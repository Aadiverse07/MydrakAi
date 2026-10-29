"""Application-level guard for any future live SAM scan attempts.

Offline-only scaffolding: this module performs no network I/O, holds no
credentials, and implements no API client. It exists so that a future live
test campaign can be bounded BEFORE any dispatch code exists.

Contract:

- Live mode is disabled by default. A campaign starts unauthorized, and
  every dispatch attempt must first call ``authorize_attempt`` with the
  scope the attempt claims.
- Authorization is an explicit LOCAL OPERATOR GATE, not cryptographic
  authentication: there is no trusted issuer in this offline project.
  ``authorize_campaign`` requires a non-empty approval token, a campaign
  ID, a scope label, and a validity window. Only the SHA-256 fingerprint
  of the token is retained — never the token itself — and fingerprints
  are single-use: a reused token is rejected. The gate cannot verify who
  typed the token.
- Every authorization is bound to one campaign ID and one approved scope.
  ``authorize_attempt`` rejects missing, mismatched, or expired
  authorization before anything is counted.
- At most five authorized attempts per authorization epoch. Each call to
  ``authorize_attempt`` counts one attempt BEFORE the caller dispatches
  anything, so failures and timeouts still consume the budget and can
  never trigger another request automatically.
- Counting the fifth attempt trips a persistent circuit breaker for the
  campaign. Every later call is rejected before any dispatch.
- There is no automatic reset and no retry helper. ``reset_campaign``
  requires an explicit operator confirmation plus a NEW, never-before-used
  approval token, clears the operational state (but never the
  single-use-token history), and returns the guard to the unauthorized
  state — the operator must authorize again. Timeouts and ambiguous
  outcomes are the caller's manual-review responsibility.
- Budget state is durable: attempt counts, breaker state, scope, expiry,
  and the used-token history live in one JSON file per campaign under a
  configurable local state directory (default: XDG data home
  ``mydrak/guard/``, never the repository). Writes are atomic
  (temp file + fsync + rename) under a lock-directory mutex; concurrent
  attempts serialize, and lock contention fails closed. A fresh guard
  object (or a restarted process) pointing at the same directory resumes
  the same budget. Corrupt, inconsistent, or unwritable state fails
  closed — the counter is never silently reset. If the state or lock file
  itself must go away (including a stale lock left by a killed process),
  deleting it is an explicit operator action performed outside this
  module.
- Loss and rollback detection is best-effort within one process: this
  module remembers the highest budget state it has ever observed per
  campaign, so a deleted or replaced state file is rejected while the
  process lives. See "Threat model" below for what this does not cover.
- The guard is pure stdlib logic with no network dependency, so it
  unit-tests without any client.

Threat model (narrowed, load-bearing): this file protects the attempt
budget against accidents, crashes, bugs, and same-flow misuse. It does
NOT defend against an actor with write access to the state directory
(they can delete or replace state; after a process restart that is
undetectable locally), against malicious Python code in the same
process (it can call or bypass anything here), or against OS/power loss.
The local file and the token fingerprints are NOT cryptographic
authorization, tamper-proof storage, or an independent trust anchor —
the fingerprints only make accidental token reuse detectable, and only
while this process lives or the state file survives.

Billing disclaimer (load-bearing): this limit bounds dispatch attempts
made through code that honors the guard. It CANNOT enforce Meta account
billing limits, observe spend, or prevent charges from other tools,
retries elsewhere, or provider-side behavior. Never present it as a
spending cap. The file lock guards against process crash races, not
operating-system or power loss.
"""


import contextlib
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any


class LiveGuardError(ValueError):
    """Raised when a live attempt is not authorized or the breaker tripped."""


#: Maximum authorized live scan attempts per authorization epoch. Local
#: project bound, not a Meta limit.
MAX_LIVE_ATTEMPTS = 5

#: Seconds to wait for the state lock before failing closed.
LOCK_TIMEOUT_SECONDS = 5.0

#: State format version. Anything else is rejected as inconsistent.
_STATE_VERSION = 1

#: Upper bound on retained single-use token fingerprints (fail closed past it).
_MAX_USED_TOKENS = 1000

_CAMPAIGN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

# In-process memory of the highest budget state ever observed per
# (state directory, campaign). Survives object recreation but not process
# restart: lets this process reject a deleted or rolled-back state file.
# This is a tripwire for accidents and same-flow misuse, not a trust
# anchor — anyone who can also restart the process defeats it.
_KNOWN: dict[tuple[str, str], dict] = {}


def _known_key(state_dir: Path, campaign_id: str) -> tuple[str, str]:
    return (str(state_dir), campaign_id)


def _note_known(state_dir: Path, campaign_id: str, state: dict) -> None:
    """Merge an observed state upward into process memory."""
    entry = _KNOWN.setdefault(
        _known_key(state_dir, campaign_id),
        {"attempts": 0, "tripped": False, "fingerprints": set()},
    )
    entry["attempts"] = max(entry["attempts"], state["attempts"])
    entry["tripped"] = entry["tripped"] or state["tripped"]
    entry["fingerprints"] = entry["fingerprints"] | set(state["used_token_fingerprints"])


def _reset_known(state_dir: Path, campaign_id: str, fingerprints: list) -> None:
    """Re-baseline the budget after an explicit operator reset.

    Attempts and breaker return to zero; the fingerprint history only
    ever grows (union), so used tokens stay dead across resets.
    """
    key = _known_key(state_dir, campaign_id)
    entry = _KNOWN.setdefault(
        key, {"attempts": 0, "tripped": False, "fingerprints": set()}
    )
    entry["attempts"] = 0
    entry["tripped"] = False
    entry["fingerprints"] = entry["fingerprints"] | set(fingerprints)


def _known_fingerprints(state_dir: Path, campaign_id: str) -> set:
    entry = _KNOWN.get(_known_key(state_dir, campaign_id))
    return set() if entry is None else set(entry["fingerprints"])


def _check_against_known(
    state_dir: Path, campaign_id: str, loaded: dict | None
) -> None:
    """Reject deleted or rolled-back state while this process has memory."""
    known = _KNOWN.get(_known_key(state_dir, campaign_id))
    if known is None:
        return
    if loaded is None:
        raise LiveGuardError("guard state is missing after prior use; failing closed")
    if loaded["attempts"] < known["attempts"]:
        raise LiveGuardError("guard state rollback detected; failing closed")
    if known["tripped"] and not loaded["tripped"]:
        raise LiveGuardError("guard state rollback detected; failing closed")
    if not known["fingerprints"] <= set(loaded["used_token_fingerprints"]):
        raise LiveGuardError(
            "guard authorization history rollback detected; failing closed"
        )


def default_state_dir() -> Path:
    """Local guard-state location. Never the repository, never committed."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return Path(base) / "mydrak" / "guard"


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _check_state(state: Any, campaign_id: str) -> dict:
    """Validate a loaded state document or raise (fail closed)."""
    if not isinstance(state, dict):
        raise LiveGuardError("guard state is corrupt")
    try:
        version = state["version"]
        stored_id = state["campaign_id"]
        scope = state["scope"]
        authorized = state["authorized"]
        attempts = state["attempts"]
        tripped = state["tripped"]
        expires_at = state["expires_at"]
        used = state["used_token_fingerprints"]
    except KeyError:
        raise LiveGuardError("guard state is corrupt") from None
    if (
        version != _STATE_VERSION
        or stored_id != campaign_id
        or not isinstance(scope, str)
        or not isinstance(authorized, bool)
        or isinstance(attempts, bool)
        or not isinstance(attempts, int)
        or not 0 <= attempts <= MAX_LIVE_ATTEMPTS
        or not isinstance(tripped, bool)
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, (int, float))
        or not isinstance(used, list)
        or not all(isinstance(item, str) for item in used)
    ):
        raise LiveGuardError("guard state is inconsistent")
    if (attempts >= MAX_LIVE_ATTEMPTS) != tripped:
        raise LiveGuardError("guard state is inconsistent")
    if not authorized and (attempts != 0 or tripped or scope != ""):
        raise LiveGuardError("guard state is inconsistent")
    return state


@contextlib.contextmanager
def _locked(state_dir: Path, campaign_id: str):
    """Mutex via atomic directory creation. Contention fails closed."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise LiveGuardError("guard state location is unwritable") from None
    lock_path = state_dir / f"{campaign_id}.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            os.mkdir(lock_path)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LiveGuardError("guard state is locked; failing closed") from None
            time.sleep(0.01)
    try:
        yield
    finally:
        try:
            os.rmdir(lock_path)
        except OSError:
            pass


class LiveCampaignGuard:
    """Durable per-campaign attempt budget with a persistent breaker.

    All mutable state lives in ``{state_dir}/{campaign_id}.json`` and is
    reloaded under lock on every operation, so recreated objects and
    restarted processes share one budget. No counter is cached.
    """

    def __init__(self, *, campaign_id: str, state_dir: str | Path | None = None) -> None:
        if not isinstance(campaign_id, str) or _CAMPAIGN_RE.fullmatch(campaign_id) is None:
            raise LiveGuardError("campaign ID must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
        self._campaign_id = campaign_id
        # Resolve symlinks so equivalent spellings share one budget entry.
        raw_dir = Path(state_dir) if state_dir is not None else default_state_dir()
        self._state_dir = Path(os.path.realpath(raw_dir))
        self._state_path = self._state_dir / f"{campaign_id}.json"
        self._lock_path = self._state_dir / f"{campaign_id}.lock"

    @property
    def campaign_id(self) -> str:
        """Campaign this guard instance is bound to."""
        return self._campaign_id

    def _read(self) -> dict | None:
        """Load and validate state.

        A missing file is a fresh campaign only when this process has no
        memory of the campaign; otherwise it is state loss and fails
        closed. Every successful load is merged into process memory.
        """
        try:
            raw = self._state_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            _check_against_known(self._state_dir, self._campaign_id, None)
            return None
        except OSError:
            raise LiveGuardError("guard state is unreadable") from None
        try:
            state = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise LiveGuardError("guard state is corrupt") from None
        checked = _check_state(state, self._campaign_id)
        _check_against_known(self._state_dir, self._campaign_id, checked)
        _note_known(self._state_dir, self._campaign_id, checked)
        return checked

    def _write(self, state: dict) -> None:
        """Persist state atomically. Any failure fails closed.

        The temp name is unique per process; the lock-directory mutex
        (held by every caller) is what serializes writers, so a
        predictable name cannot collide in practice. A stale temp file
        from a killed process is truncated under lock before use and can
        never be renamed by anyone but its writer.
        """
        tmp_path = None
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self._state_dir / f"{self._campaign_id}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._state_path)
        except OSError:
            raise LiveGuardError("guard state is unwritable") from None
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        _note_known(self._state_dir, self._campaign_id, state)

    def _fresh_state(self) -> dict:
        return {
            "version": _STATE_VERSION,
            "campaign_id": self._campaign_id,
            "scope": "",
            "authorized": False,
            "attempts": 0,
            "tripped": False,
            "expires_at": 0.0,
            "used_token_fingerprints": [],
        }

    def _is_expired(self, state: dict) -> bool:
        return time.time() >= state["expires_at"]

    @property
    def authorized(self) -> bool:
        """Whether the campaign currently holds an unexpired authorization."""
        state = self._read()
        return state is not None and state["authorized"] and not self._is_expired(state)

    @property
    def scope(self) -> str:
        """Scope label of the current authorization, or empty."""
        state = self._read()
        if state is None or not state["authorized"] or self._is_expired(state):
            return ""
        return state["scope"]

    @property
    def attempts_used(self) -> int:
        """Attempts counted so far, including failed and timed-out ones."""
        state = self._read()
        return 0 if state is None else state["attempts"]

    @property
    def breaker_tripped(self) -> bool:
        """Whether the campaign breaker has tripped (persistent)."""
        state = self._read()
        return state is not None and state["tripped"]

    @property
    def attempts_remaining(self) -> int:
        """Authorized attempts still available before the breaker trips."""
        return max(0, MAX_LIVE_ATTEMPTS - self.attempts_used)

    def authorize_campaign(
        self,
        *,
        approval_token: str,
        scope: str,
        valid_seconds: float = 3600.0,
    ) -> None:
        """Enable live attempts for this campaign ID and scope.

        Explicit local operator gate: the token is checked for shape and
        single-use only — this does not authenticate anyone. Scope binds
        every later attempt. Expired authorizations may be replaced;
        active ones require a reset first.
        """
        if not isinstance(approval_token, str) or not approval_token:
            raise LiveGuardError("a non-empty approval token is required")
        if not isinstance(scope, str) or not scope:
            raise LiveGuardError("a non-empty authorization scope is required")
        if (
            isinstance(valid_seconds, bool)
            or not isinstance(valid_seconds, (int, float))
            or not math.isfinite(valid_seconds)
            or valid_seconds < 0
        ):
            raise LiveGuardError("validity window must be a finite non-negative number")
        fingerprint = _fingerprint(approval_token)
        with _locked(self._state_dir, self._campaign_id):
            # _read enforces process-memory history as a subset of the
            # on-disk history, so the disk check below covers both.
            state = self._read()
            if state is None:
                state = self._fresh_state()
            if len(state["used_token_fingerprints"]) >= _MAX_USED_TOKENS:
                raise LiveGuardError("authorization history is full; failing closed")
            if fingerprint in state["used_token_fingerprints"]:
                raise LiveGuardError("approval token was already used")
            if state["authorized"] and not self._is_expired(state):
                raise LiveGuardError("campaign already authorized: reset first")
            if state["tripped"]:
                raise LiveGuardError("breaker tripped: reset requires operator action")
            state["used_token_fingerprints"] = state["used_token_fingerprints"] + [fingerprint]
            state["scope"] = scope
            state["authorized"] = True
            state["expires_at"] = time.time() + valid_seconds
            self._write(state)

    def authorize_attempt(self, *, scope: str) -> int:
        """Count one dispatch attempt BEFORE the caller sends anything.

        The claimed scope must equal the authorized scope, and the
        authorization must be present and unexpired. Returns the 1-based
        attempt number. Counting the fifth attempt trips the breaker
        immediately. Every rejection happens before anything is counted.
        """
        if not isinstance(scope, str) or not scope:
            raise LiveGuardError("attempt scope is required")
        with _locked(self._state_dir, self._campaign_id):
            state = self._read()
            if state is None or not state["authorized"]:
                raise LiveGuardError("live mode is disabled: no campaign authorization")
            if self._is_expired(state):
                raise LiveGuardError("campaign authorization expired")
            if scope != state["scope"]:
                raise LiveGuardError("attempt scope does not match the authorization")
            if state["tripped"]:
                raise LiveGuardError("breaker tripped: no further attempts allowed")
            if state["attempts"] >= MAX_LIVE_ATTEMPTS:
                state["tripped"] = True
                self._write(state)
                raise LiveGuardError("attempt budget exhausted: breaker tripped")
            state["attempts"] += 1
            if state["attempts"] >= MAX_LIVE_ATTEMPTS:
                state["tripped"] = True
            self._write(state)
            return state["attempts"]

    def reset_campaign(self, *, operator_confirmed: bool, new_approval_token: str) -> None:
        """Return to the unauthorized state after explicit operator action.

        Requires a deliberate confirmation flag and a NEW, never-before-used
        approval token. Operational state (authorization, scope, attempts,
        breaker) is cleared; the single-use-token history is retained so
        old tokens stay dead. Reset only verifies distinctness — the new
        token is recorded as used when the follow-up authorization consumes
        it. The caller must then authorize again. If the state file is
        missing, reset re-seeds the on-disk history from process memory
        and starts a new epoch at zero: the lost budget is not recovered,
        and old tokens stay dead while this process lives. A present but
        corrupt state file cannot be reset through this call — removing it
        is a separate explicit operator action outside this module.
        """
        if operator_confirmed is not True:
            raise LiveGuardError("reset requires explicit operator confirmation")
        if not isinstance(new_approval_token, str) or not new_approval_token:
            raise LiveGuardError("reset requires a new non-empty approval token")
        fingerprint = _fingerprint(new_approval_token)
        with _locked(self._state_dir, self._campaign_id):
            try:
                state = self._read()
            except LiveGuardError:
                if self._state_path.exists():
                    raise
                # Missing file: explicit operator recovery. Re-seed history
                # from process memory so old tokens stay dead; the budget
                # restarts at zero and is not recovered.
                state = self._fresh_state()
                state["used_token_fingerprints"] = sorted(
                    _known_fingerprints(self._state_dir, self._campaign_id)
                )
            if state is None:
                state = self._fresh_state()
            if fingerprint in state["used_token_fingerprints"]:
                raise LiveGuardError("reset token was already used")
            state["scope"] = ""
            state["authorized"] = False
            state["attempts"] = 0
            state["tripped"] = False
            state["expires_at"] = 0.0
            self._write(state)
            # Explicit operator action: re-baseline process memory so the
            # legitimate clear is not mistaken for a rollback. Histories
            # (used tokens) are retained, never dropped.
            _reset_known(
                self._state_dir, self._campaign_id, state["used_token_fingerprints"]
            )

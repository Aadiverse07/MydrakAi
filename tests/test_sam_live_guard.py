"""Live-guard and mock-transport tests. No network exists in this path:
every reply comes from the deterministic fake and every fixture is synthetic."""

import json
import threading
from pathlib import Path

import pytest

from mydrak.sam.guard import (
    MAX_LIVE_ATTEMPTS,
    LiveCampaignGuard,
    LiveGuardError,
    default_state_dir,
)
from mydrak.sam.transport import (
    MOCK_PROVENANCE,
    FakeSamTransport,
    MockScanResult,
    SamScanRequest,
    SamScanResponse,
    SamTransport,
    SamTransportError,
    default_transport,
    request_live_transport,
    run_scan,
)

SCOPE = "test-campaign-scope"


def make_guard(tmp_path, campaign_id="campaign-1", **kwargs):
    return LiveCampaignGuard(campaign_id=campaign_id, state_dir=tmp_path / "guard", **kwargs)


def authorized_guard(tmp_path, campaign_id="campaign-1", scope=SCOPE, **kwargs):
    guard = make_guard(tmp_path, campaign_id)
    guard.authorize_campaign(approval_token="operator-token", scope=scope, **kwargs)
    return guard


def scan_request(prompt="green leaf", scope=SCOPE):
    return SamScanRequest(
        image_id="synthetic-leaf-001",
        image_source_license="synthetic fixture, no rights needed",
        prompt=prompt,
        scope=scope,
    )


def run_dims(**kwargs):
    return dict(expected_width=640, expected_height=480, **kwargs)


def test_live_mode_disabled_by_default(tmp_path):
    guard = make_guard(tmp_path)
    assert guard.authorized is False
    assert guard.attempts_remaining == MAX_LIVE_ATTEMPTS
    with pytest.raises(LiveGuardError):
        guard.authorize_attempt(scope=SCOPE)


def test_campaign_id_rejects_traversal(tmp_path):
    with pytest.raises(LiveGuardError):
        LiveCampaignGuard(campaign_id="../escape", state_dir=tmp_path)
    with pytest.raises(LiveGuardError):
        LiveCampaignGuard(campaign_id="", state_dir=tmp_path)


def test_default_state_dir_is_local_and_not_repo():
    target = default_state_dir()
    assert target.parts[-2:] == ("mydrak", "guard")
    assert "Mydrak_Ai" not in target.parts


def test_default_state_dir_honors_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_state_dir() == tmp_path / "mydrak" / "guard"


def test_authorization_requires_token_scope_window(tmp_path):
    guard = make_guard(tmp_path)
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token="", scope=SCOPE)
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token="tok", scope="")
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token=None, scope=SCOPE)
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token="tok", scope=SCOPE, valid_seconds=True)
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token="tok", scope=SCOPE, valid_seconds=float("inf"))
    with pytest.raises(LiveGuardError):
        guard.authorize_campaign(approval_token="tok", scope=SCOPE, valid_seconds=-1)
    guard.authorize_campaign(approval_token="tok", scope=SCOPE)
    assert guard.authorized is True
    assert guard.scope == SCOPE


def test_token_never_stored(tmp_path):
    guard = authorized_guard(tmp_path)
    state_file = tmp_path / "guard" / "campaign-1.json"
    assert "operator-token" not in state_file.read_text(encoding="utf-8")
    assert "operator-token" not in repr(guard)


def test_expired_authorization_rejected(tmp_path):
    guard = make_guard(tmp_path)
    guard.authorize_campaign(approval_token="tok", scope=SCOPE, valid_seconds=0)
    assert guard.authorized is False
    with pytest.raises(LiveGuardError, match="expired"):
        guard.authorize_attempt(scope=SCOPE)
    assert guard.attempts_used == 0


def test_scope_mismatch_rejected_before_counting(tmp_path):
    guard = authorized_guard(tmp_path)
    with pytest.raises(LiveGuardError, match="scope"):
        guard.authorize_attempt(scope="other-scope")
    with pytest.raises(LiveGuardError):
        guard.authorize_attempt(scope="")
    assert guard.attempts_used == 0
    assert guard.authorize_attempt(scope=SCOPE) == 1


def test_token_reuse_rejected(tmp_path):
    guard = make_guard(tmp_path)
    guard.authorize_campaign(approval_token="tok", scope=SCOPE)
    guard.reset_campaign(operator_confirmed=True, new_approval_token="tok2")
    with pytest.raises(LiveGuardError, match="already used"):
        guard.authorize_campaign(approval_token="tok", scope=SCOPE)
    guard.authorize_campaign(approval_token="tok2", scope=SCOPE)
    with pytest.raises(LiveGuardError, match="already used"):
        guard.reset_campaign(operator_confirmed=True, new_approval_token="tok2")


def test_double_authorize_rejected_without_reset(tmp_path):
    guard = authorized_guard(tmp_path)
    with pytest.raises(LiveGuardError, match="already authorized"):
        guard.authorize_campaign(approval_token="tok2", scope=SCOPE)


def test_attempts_one_through_five_then_breaker(tmp_path):
    assert MAX_LIVE_ATTEMPTS == 5
    guard = authorized_guard(tmp_path)
    for expected in (1, 2, 3, 4, 5):
        assert guard.authorize_attempt(scope=SCOPE) == expected
    assert guard.breaker_tripped is True
    assert guard.attempts_remaining == 0
    with pytest.raises(LiveGuardError):
        guard.authorize_attempt(scope=SCOPE)


def test_budget_survives_recreation_and_restart(tmp_path):
    guard = authorized_guard(tmp_path)
    assert guard.authorize_attempt(scope=SCOPE) == 1
    assert guard.authorize_attempt(scope=SCOPE) == 2
    recreated = make_guard(tmp_path)
    assert recreated.attempts_used == 2
    assert recreated.authorized is True
    assert recreated.scope == SCOPE
    assert recreated.authorize_attempt(scope=SCOPE) == 3
    assert recreated.authorize_attempt(scope=SCOPE) == 4
    assert recreated.authorize_attempt(scope=SCOPE) == 5
    assert recreated.breaker_tripped is True
    restarted = make_guard(tmp_path)
    assert restarted.breaker_tripped is True
    with pytest.raises(LiveGuardError):
        restarted.authorize_attempt(scope=SCOPE)


def test_corrupt_state_fails_closed(tmp_path):
    guard = authorized_guard(tmp_path)
    assert guard.authorize_attempt(scope=SCOPE) == 1
    state_file = tmp_path / "guard" / "campaign-1.json"
    state_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(LiveGuardError, match="corrupt"):
        make_guard(tmp_path).authorize_attempt(scope=SCOPE)
    with pytest.raises(LiveGuardError):
        make_guard(tmp_path).authorize_campaign(approval_token="tok2", scope=SCOPE)


def test_inconsistent_state_fails_closed(tmp_path):
    authorized_guard(tmp_path)
    state_file = tmp_path / "guard" / "campaign-1.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["tripped"] = True
    state_file.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(LiveGuardError, match="inconsistent"):
        make_guard(tmp_path).authorize_attempt(scope=SCOPE)


def test_missing_state_after_use_fails_closed(tmp_path):
    guard = authorized_guard(tmp_path)
    assert guard.authorize_attempt(scope=SCOPE) == 1
    (tmp_path / "guard" / "campaign-1.json").unlink()
    with pytest.raises(LiveGuardError, match="missing after prior use"):
        guard.authorize_attempt(scope=SCOPE)
    # A recreated object in the same process shares the memory: no silent
    # fresh start. (After a process restart this is undetectable locally
    # and documented as a residual limitation.)
    with pytest.raises(LiveGuardError, match="missing after prior use"):
        make_guard(tmp_path).authorized


def test_state_dir_creation_failure_surfaces_guard_error(tmp_path, monkeypatch):
    from pathlib import Path
    calls = []
    real_mkdir = Path.mkdir
    def fail_second_mkdir(self, *args, **kwargs):
        calls.append(1)
        if len(calls) >= 2:
            raise OSError("disk full")
        return real_mkdir(self, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", fail_second_mkdir)
    guard = make_guard(tmp_path)
    with pytest.raises(LiveGuardError) as excinfo:
        guard.authorize_campaign(approval_token="tok", scope=SCOPE)
    # Exact type: a cleanup UnboundLocalError must not mask the guard error.
    assert type(excinfo.value) is LiveGuardError
    assert guard.authorized is False
    assert not (tmp_path / "guard" / "campaign-1.json").exists()
    # No authorization was granted, so the scan path stays closed.
    transport = default_transport()
    with pytest.raises(LiveGuardError):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert transport.sent_count == 0


def test_unwritable_state_fails_closed(tmp_path, monkeypatch):
    guard = authorized_guard(tmp_path)
    def fail_replace(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr("os.replace", fail_replace)
    with pytest.raises(LiveGuardError, match="unwritable"):
        guard.authorize_attempt(scope=SCOPE)
    monkeypatch.undo()
    # The attempt was rejected before any dispatch, so nothing was counted:
    # durability failure fails closed instead of counting without recording.
    assert make_guard(tmp_path).attempts_used == 0


def test_rolled_back_state_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    state_file = tmp_path / "guard" / "campaign-1.json"
    assert guard.authorize_attempt(scope=SCOPE) == 1
    earlier = state_file.read_bytes()
    assert guard.authorize_attempt(scope=SCOPE) == 2
    state_file.write_bytes(earlier)
    with pytest.raises(LiveGuardError, match="rollback detected"):
        make_guard(tmp_path).authorize_attempt(scope=SCOPE)


def test_tripped_rollback_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    state_file = tmp_path / "guard" / "campaign-1.json"
    for _ in range(4):
        guard.authorize_attempt(scope=SCOPE)
    earlier = state_file.read_bytes()
    assert guard.authorize_attempt(scope=SCOPE) == 5
    assert guard.breaker_tripped is True
    state_file.write_bytes(earlier)
    with pytest.raises(LiveGuardError, match="rollback detected"):
        make_guard(tmp_path).authorize_attempt(scope=SCOPE)


def test_token_reuse_after_state_loss_rejected(tmp_path):
    guard = make_guard(tmp_path)
    guard.authorize_campaign(approval_token="tokA", scope=SCOPE)
    snapshot = (tmp_path / "guard" / "campaign-1.json").read_bytes()
    guard.reset_campaign(operator_confirmed=True, new_approval_token="tokB")
    guard.authorize_campaign(approval_token="tokB", scope=SCOPE)
    (tmp_path / "guard" / "campaign-1.json").write_bytes(snapshot)
    # On-disk history lost tokB: fail closed on the rollback itself.
    with pytest.raises(LiveGuardError, match="rollback detected"):
        make_guard(tmp_path).authorize_campaign(approval_token="tokC", scope=SCOPE)
    # Deleting the file does not resurrect tokB either.
    (tmp_path / "guard" / "campaign-1.json").unlink()
    with pytest.raises(LiveGuardError, match="already used"):
        make_guard(tmp_path).reset_campaign(
            operator_confirmed=True, new_approval_token="tokB"
        )
    # Explicit recovery with a fresh token starts a new epoch at zero;
    # the lost budget is not recovered.
    make_guard(tmp_path).reset_campaign(operator_confirmed=True, new_approval_token="tokC")
    fresh = make_guard(tmp_path)
    fresh.authorize_campaign(approval_token="tokC", scope=SCOPE)
    assert fresh.authorize_attempt(scope=SCOPE) == 1


def test_symlinked_state_dir_shares_budget(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    guard = LiveCampaignGuard(campaign_id="campaign-1", state_dir=link)
    guard.authorize_campaign(approval_token="tok", scope=SCOPE)
    assert guard.authorize_attempt(scope=SCOPE) == 1
    via_real = LiveCampaignGuard(campaign_id="campaign-1", state_dir=real)
    assert via_real.attempts_used == 1
    assert via_real.authorize_attempt(scope=SCOPE) == 2


def test_stale_lock_fails_closed_without_auto_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr("mydrak.sam.guard.LOCK_TIMEOUT_SECONDS", 0.2)
    guard = authorized_guard(tmp_path)
    lock_dir = tmp_path / "guard" / "campaign-1.lock"
    lock_dir.mkdir(parents=True)
    with pytest.raises(LiveGuardError, match="locked"):
        guard.authorize_attempt(scope=SCOPE)
    assert guard.attempts_used == 0
    # Explicit operator recovery only: removing the lock dir by hand.
    lock_dir.rmdir()
    assert guard.authorize_attempt(scope=SCOPE) == 1


def test_orphan_temp_file_does_not_break_writes(tmp_path):
    guard = authorized_guard(tmp_path)
    (tmp_path / "guard" / "campaign-1.tmp.99999").write_text("stale", encoding="utf-8")
    assert guard.authorize_attempt(scope=SCOPE) == 1
    assert make_guard(tmp_path).attempts_used == 1


def test_cross_process_contention_counts_exactly_five(tmp_path):
    import subprocess
    import sys
    guard = authorized_guard(tmp_path, campaign_id="xproc")
    assert guard.authorize_attempt(scope=SCOPE) == 1
    script = "\n".join([
        "import sys",
        "sys.path.insert(0, 'src')",
        "from mydrak.sam.guard import LiveCampaignGuard, LiveGuardError",
        f"g = LiveCampaignGuard(campaign_id='xproc', state_dir={str(tmp_path / 'guard')!r})",
        "out = []",
        "for _ in range(3):",
        "    try:",
        f"        out.append(str(g.authorize_attempt(scope={SCOPE!r})))",
        "    except LiveGuardError:",
        "        out.append('ERR')",
        "print(' '.join(out), flush=True)",
    ])
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for _ in range(3)
    ]
    outs = []
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=120)
        assert proc.returncode == 0, stderr
        outs.extend(stdout.split())
    # One attempt was already counted in-process; the three subprocesses
    # share the remaining budget of four: exactly attempts 2-5 succeed.
    assert sorted(n for n in outs if n != "ERR") == ["2", "3", "4", "5"]
    assert outs.count("ERR") == 5
    final = make_guard(tmp_path, campaign_id="xproc")
    assert final.attempts_used == 5
    assert final.breaker_tripped is True


def test_concurrent_attempts_count_exactly_five(tmp_path):
    guard = authorized_guard(tmp_path)
    successes = []
    failures = []
    floodgate = threading.Barrier(9)
    def worker():
        floodgate.wait()
        for _ in range(10):
            try:
                successes.append(guard.authorize_attempt(scope=SCOPE))
            except LiveGuardError:
                failures.append(1)
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    floodgate.wait()
    for thread in threads:
        thread.join()
    assert sorted(successes) == [1, 2, 3, 4, 5]
    assert len(failures) == 8 * 10 - 5
    assert make_guard(tmp_path).attempts_used == 5
    assert make_guard(tmp_path).breaker_tripped is True


def test_timeout_consumes_attempt_without_retry(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = FakeSamTransport(mode="timeout")
    with pytest.raises(SamTransportError, match="manual review"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert guard.attempts_used == 1
    assert transport.sent_count == 1
    with pytest.raises(SamTransportError, match="manual review"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert guard.attempts_used == 2
    assert transport.sent_count == 2


def test_five_timeouts_trip_breaker_then_reject(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = FakeSamTransport(mode="timeout")
    for _ in range(5):
        with pytest.raises(SamTransportError, match="manual review"):
            run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert guard.breaker_tripped is True
    with pytest.raises(LiveGuardError):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert transport.sent_count == 5


def test_no_automatic_reset(tmp_path):
    guard = authorized_guard(tmp_path)
    for _ in range(5):
        guard.authorize_attempt(scope=SCOPE)
    assert guard.breaker_tripped is True
    with pytest.raises(LiveGuardError):
        guard.reset_campaign(operator_confirmed=False, new_approval_token="tok2")
    with pytest.raises(LiveGuardError):
        guard.reset_campaign(operator_confirmed=True, new_approval_token="")
    assert guard.breaker_tripped is True
    guard.reset_campaign(operator_confirmed=True, new_approval_token="tok2")
    assert guard.authorized is False
    assert guard.attempts_used == 0
    with pytest.raises(LiveGuardError):
        guard.authorize_attempt(scope=SCOPE)
    guard.authorize_campaign(approval_token="tok2", scope=SCOPE)
    assert guard.authorize_attempt(scope=SCOPE) == 1


def test_default_transport_is_fake_and_live_unavailable():
    assert isinstance(default_transport(), FakeSamTransport)
    with pytest.raises(SamTransportError, match="no live SAM transport"):
        request_live_transport()


def test_custom_transport_rejected_before_send(tmp_path):
    sent = []
    class SneakyTransport(SamTransport):
        def send(self, request):
            sent.append(request)
            return SamScanResponse(request_id="live-1", output_text="", is_mock=True)
    guard = authorized_guard(tmp_path)
    with pytest.raises(SamTransportError, match="only the fake transport"):
        run_scan(guard=guard, transport=SneakyTransport(),
                 request=scan_request(), **run_dims())
    assert sent == []
    assert guard.attempts_used == 0


def test_fake_subclass_rejected_before_send(tmp_path):
    sent = []
    class ChildFake(FakeSamTransport):
        def send(self, request):
            sent.append(request)
            return super().send(request)
    guard = authorized_guard(tmp_path)
    with pytest.raises(SamTransportError, match="only the fake transport"):
        run_scan(guard=guard, transport=ChildFake(), request=scan_request(), **run_dims())
    assert sent == []
    assert guard.attempts_used == 0


def test_monkeypatched_send_with_forged_reply_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    transport.send = lambda request: SamScanResponse(
        request_id="live-1", output_text="", is_mock=True
    )
    with pytest.raises(SamTransportError, match="provenance checks"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    # The forged reply was received, so the attempt that fetched it is spent.
    assert guard.attempts_used == 1


def test_monkeypatched_send_with_wrong_type_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    transport.send = lambda request: {"is_mock": True, "output_text": ""}
    with pytest.raises(SamTransportError, match="provenance checks"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert guard.attempts_used == 1


def test_monkeypatched_send_with_non_string_payload_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    transport.send = lambda request: SamScanResponse(
        request_id="fake-9", output_text=123, is_mock=True
    )
    with pytest.raises(SamTransportError, match="provenance checks"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())


def test_shape_valid_forgery_passes_proving_boundary_limit(tmp_path):
    # Documents the boundary honestly: a shape-valid reply forged by
    # same-process code is indistinguishable from the fake's own output,
    # so it parses. The gate, type checks, and reply validation stop
    # accidents and misconfiguration — not an in-process forger.
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    transport.send = lambda request: SamScanResponse(
        request_id="fake-99", output_text="", is_mock=True
    )
    result = run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())
    assert result.provenance == "synthetic-mock"
    assert result.frame.match_count == 0
    assert guard.attempts_used == 1


def test_cleared_mock_flag_rejected(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    transport.send = lambda request: SamScanResponse(
        request_id="fake-9", output_text="", is_mock=False
    )
    with pytest.raises(SamTransportError, match="provenance checks"):
        run_scan(guard=guard, transport=transport, request=scan_request(), **run_dims())


def test_provenance_rejects_non_mock_values():
    from mydrak.sam.response_text import SamFrame
    frame = SamFrame(frame_index=0, image_width=1, image_height=1, objects=())
    for bad in ("live", "", None, True):
        with pytest.raises(SamTransportError):
            MockScanResult(frame=frame, provenance=bad, request_id="fake-1", scope=SCOPE)


def test_result_rejects_invalid_frame():
    from mydrak.sam.response_text import SamFrame
    good = SamFrame(frame_index=0, image_width=1, image_height=1, objects=())
    for bad_frame in (None, "not-a-frame", {"frame": 1}, 42, ["x"]):
        with pytest.raises(SamTransportError, match="frame must be a SamFrame"):
            MockScanResult(
                frame=bad_frame, provenance=MOCK_PROVENANCE,
                request_id="fake-1", scope=SCOPE,
            )
    control = MockScanResult(
        frame=good, provenance=MOCK_PROVENANCE, request_id="fake-1", scope=SCOPE
    )
    assert control.frame is good
    assert control.provenance == "synthetic-mock"


def test_mock_scan_result_carries_provenance(tmp_path):
    guard = authorized_guard(tmp_path)
    result = run_scan(
        guard=guard, transport=default_transport(), request=scan_request(), **run_dims()
    )
    assert isinstance(result, MockScanResult)
    assert result.provenance == MOCK_PROVENANCE == "synthetic-mock"
    from mydrak.sam.response_text import SamFrame
    assert isinstance(result.frame, SamFrame)
    assert result.frame.match_count == 0
    assert result.scope == SCOPE
    assert result.request_id.startswith("fake-")
    second = run_scan(
        guard=guard, transport=default_transport(), request=scan_request(), **run_dims()
    )
    assert second.frame.match_count == 0
    assert guard.attempts_used == 2


def test_provenance_cannot_claim_live():
    with pytest.raises(SamTransportError):
        MockScanResult(frame=None, provenance="live", request_id="x", scope=SCOPE)


def test_mock_fixture_record_parses_with_provenance(tmp_path):
    fixture = (
        "<0f>0<|box;x1=10;y1=20;x2=100;y2=200;w=640;h=480|>"
        "<|mask;x=0;y=0;data=120,160,~abc12|>"
    )
    guard = authorized_guard(tmp_path)
    out = run_scan(
        guard=guard,
        transport=FakeSamTransport(fixture_text=fixture),
        request=scan_request(),
        **run_dims(),
    )
    assert out.provenance == "synthetic-mock"
    assert out.frame.match_count == 1
    assert out.frame.objects[0].mask.payload == "abc12"


def test_malformed_reply_needs_manual_review(tmp_path):
    guard = authorized_guard(tmp_path)
    with pytest.raises(SamTransportError, match="manual review"):
        run_scan(
            guard=guard,
            transport=FakeSamTransport(mode="malformed"),
            request=scan_request(),
            **run_dims(),
        )
    assert guard.attempts_used == 1


def test_scope_mismatch_rejected_before_dispatch(tmp_path):
    guard = authorized_guard(tmp_path, scope=SCOPE)
    transport = default_transport()
    with pytest.raises(LiveGuardError, match="scope"):
        run_scan(guard=guard, transport=transport,
                 request=scan_request(scope="wrong-scope"), **run_dims())
    assert guard.attempts_used == 0
    assert transport.sent_count == 0


def test_request_validation_rejects_bad_input(tmp_path):
    guard = authorized_guard(tmp_path)
    transport = default_transport()
    base = dict(image_id="i", image_source_license="s", prompt="p", scope=SCOPE)
    bad_requests = [
        SamScanRequest(**{**base, "image_id": ""}),
        SamScanRequest(**{**base, "prompt": ""}),
        SamScanRequest(**{**base, "scope": ""}),
        SamScanRequest(**{**base, "prompt": "x" * 501}),
        "not-a-request",
    ]
    for bad in bad_requests:
        with pytest.raises(SamTransportError):
            run_scan(guard=guard, transport=transport, request=bad, **run_dims())
    with pytest.raises(SamTransportError):
        run_scan(guard=guard, transport=object(), request=scan_request(), **run_dims())
    with pytest.raises(SamTransportError):
        run_scan(guard=object(), transport=transport, request=scan_request(), **run_dims())
    with pytest.raises(SamTransportError):
        run_scan(guard=guard, transport=SamTransport(), request=scan_request(), **run_dims())
    assert guard.attempts_used == 0
    assert transport.sent_count == 0


def test_run_scan_requires_guard_authorization(tmp_path):
    with pytest.raises(LiveGuardError):
        run_scan(guard=make_guard(tmp_path), transport=default_transport(),
                 request=scan_request(), **run_dims())


def test_new_modules_use_no_network_or_sdk():
    root = Path(__file__).resolve().parents[1] / "src" / "mydrak" / "sam"
    for name in ("guard.py", "transport.py"):
        source = (root / name).read_text()
        for token in ("urllib", "http.client", "socket", "subprocess",
                      "requests", "httpx", "openai", "telegram"):
            assert token not in source

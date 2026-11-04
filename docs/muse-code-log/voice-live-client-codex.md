# Guarded Muse Voice Transcribe client — Codex

Date: 2026-11-04. Offline implementation and hermetic tests only.

## Scope and changes

- Added `voice.request_path` and `voice.credential_env_var` to the existing
  user-configured section. The local 60-second, byte, sample-rate, language
  bias, and keyword values remain project-local settings.
- Added a stdlib multipart transport with redirects and retries disabled,
  bounded response reads, and safe failure categories. The client validates
  mono 24 kHz 16-bit PCM WAV, reserves the conservatively rounded-up audio
  estimate through the shared guard/ledger, and parses only the documented
  response fields. Transcript text is excluded from object representations
  and failures never include it.
- Added the temporary-file ffmpeg converter using only an argument list,
  `shell=False`, timeout, and cleanup. The injectable runner keeps tests from
  invoking ffmpeg.
- Added a synthetic two-second WAV smoke CLI. It prints status metadata only;
  transcript output requires `--show-transcript` and emits a warning to stderr.
- No Telegram voice wiring was added. The normalized update contract has no
  voice metadata/file identifier and the runner has no voice branch; the
  adapter's separate mock-only seam is not a clean transport download seam.

## Verification

- Focused combined command: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_audio_live_client.py tests/test_sam_live_client.py tests/test_sam_client.py tests/test_live_guard.py tests/test_telegram_config.py -q` — **258 passed**.
- Full suite after Part B/C: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q` — **1365 passed**.
- No smoke script, network call, ffmpeg process, or live provider call was run.
- Provider compatibility, API account access, actual billing, retention/ZDR,
  Hindi field quality, and Telegram voice-message handling remain UNVERIFIED or
  unimplemented.

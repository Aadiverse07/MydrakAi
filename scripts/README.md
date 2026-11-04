# Offline smoke CLI source

`smoke_glimmer.py` and `smoke_spark.py` are guarded, one-logical-request CLIs.
They use a tiny synthetic Glimmer JPEG or a fixed synthetic Spark text context.
They are implemented and tested only offline; this task did not run them against
providers. Each requires `--live-authorized`, `MYDRAK_LIVE=1`, a positive
`--max-spend-usd`, a persistent local spend ledger, a credential environment
variable, and complete cost configuration. Their request/response formats are
based solely on the user-supplied reference files under `docs/providers/`, and
provider/account compatibility is UNVERIFIED. Do not invoke either script until
the live-readiness gates have been approved and a separate live-call authorization
is given. A guarded SAM 3.1 streaming client and smoke CLI now exist, but no SAM
smoke request was run and live SAM remains NO-GO. An isolated guarded Voice
Transcribe client, synthetic-WAV smoke CLI, and ffmpeg converter exist; no voice
smoke was run. Telegram has a standard-library HTTP transport, but no
voice-message runner path is implemented or verified.
Failure output has one machine-readable `failure_category` and a
`request_sent=true|false` field. Guard failures include a safe condition ID;
HTTP failures include only the numeric status and standard reason phrase. No
response body, headers, request data, key, or exception text is printed.

Glimmer host selection is controlled by `glimmer_host.choice` in
`config/models.yaml`. NVIDIA is currently selected and uses `NVIDIA_API_KEY`;
the Together profile remains available and uses `TOGETHER_API_KEY`. The NVIDIA
profile and its placeholder prices are UNVERIFIED until a separate smoke test
passes. Do not send private farmer photos to NVIDIA before its retention and
privacy terms are reviewed.

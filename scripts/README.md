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
is given. SAM and voice still have no live clients; Telegram has no wire client.
Failure output has one machine-readable `failure_category` and a
`request_sent=true|false` field. Guard failures include a safe condition ID;
HTTP failures include only the numeric status and standard reason phrase. No
response body, headers, request data, key, or exception text is printed.

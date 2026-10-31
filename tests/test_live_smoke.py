"""Smoke CLI tests are refusal-path only; no request is executed."""

from scripts._live_smoke import run_smoke


class NeverCallTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("offline smoke test must not dispatch")


def test_glimmer_smoke_refuses_without_explicit_flag_and_prints_no_payload():
    transport = NeverCallTransport()
    lines = []
    code = run_smoke(
        "tier1", [], transport=transport,
        environ={"MYDRAK_LIVE": "1", "TOGETHER_API_KEY": "SYNTHETIC-SECRET"},
        output=lines.append,
    )
    assert code == 2
    assert transport.calls == 0
    assert len(lines) == 2 and "status=refused_or_failed" in lines[0]
    assert all("SYNTHETIC-SECRET" not in line for line in lines)
    assert all("data:image" not in line for line in lines)


def test_spark_smoke_refuses_by_default_and_cannot_use_contributor_privately():
    transport = NeverCallTransport()
    lines = []
    code = run_smoke(
        "tier2", [], transport=transport,
        environ={"MYDRAK_LIVE": "1", "META_API_KEY": "SYNTHETIC-SECRET"},
        output=lines.append,
    )
    assert code == 2
    assert transport.calls == 0
    assert "status=refused_or_failed" in lines[0]
    assert all("SYNTHETIC-SECRET" not in line for line in lines)

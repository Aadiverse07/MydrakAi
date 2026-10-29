"""SAM client-boundary tests. No network exists here: the only session is
a recording fake, credentials are synthetic test values, and no provider
JSON serialization is asserted (none exists)."""

import dataclasses
import json
import traceback
from pathlib import Path

import pytest
import yaml

from conftest import REPO_ROOT

from mydrak.sam.client import (
    SAM_API_BASE_URL,
    SamClientConfig,
    SamConfigError,
    SamHttpRequest,
    SamOutboundCall,
    build_http_request,
    canonical_responses_url,
    dispatch_call,
    dispatch_http,
    prepare_call,
    resolve_api_key,
    serialize_sam_body,
)
from mydrak.sam.transport import default_transport, run_scan


def valid_kwargs(**overrides):
    base = {
        "model_id": "test-sam-model",
        "endpoint": "https://sam.test.invalid/v1",
        "timeout_s": 30,
        "api_key_env_var": "TEST_SAM_API_KEY",
    }
    base.update(overrides)
    return base


def valid_config(**overrides):
    return SamClientConfig(**valid_kwargs(**overrides))


class RecordingSession:
    """Test-only session double. Records calls; performs no I/O."""

    def __init__(self, reply_text=""):
        self.calls = []
        self.reply_text = reply_text

    def submit(self, call, *, api_key):
        self.calls.append((call, api_key))
        return self.reply_text


def test_valid_config_constructs():
    config = valid_config()
    assert (config.model_id, config.endpoint, config.timeout_s) == (
        "test-sam-model", "https://sam.test.invalid/v1", 30,
    )


def test_config_from_mapping():
    config = SamClientConfig.from_mapping(valid_kwargs())
    assert config.api_key_env_var == "TEST_SAM_API_KEY"
    with pytest.raises(SamConfigError):
        SamClientConfig.from_mapping({"model_id": "m"})
    with pytest.raises(SamConfigError):
        SamClientConfig.from_mapping({**valid_kwargs(), "surprise": 1})
    with pytest.raises(SamConfigError):
        SamClientConfig.from_mapping(["not-a-mapping"])


def test_repo_placeholders_rejected():
    sam_section = yaml.safe_load(open(REPO_ROOT / "config" / "models.yaml"))["sam"]
    assert "TODO" in repr(sam_section.values())
    with pytest.raises(SamConfigError):
        SamClientConfig.from_mapping({**valid_kwargs(), "model_id": sam_section["model_id"]})
    with pytest.raises(SamConfigError):
        SamClientConfig.from_mapping({**valid_kwargs(), "endpoint": sam_section["endpoint"]})


@pytest.mark.parametrize("field,value", [
    ("model_id", ""), ("model_id", "   "), ("model_id", None), ("model_id", 123),
    ("model_id", "TODO(verify)"), ("model_id", "has space"),
    ("endpoint", ""), ("endpoint", "   "), ("endpoint", None),
    ("endpoint", "TODO(verify)"), ("endpoint", "http://plain.test/v1"),
    ("endpoint", "not a url"), ("endpoint", "notaurl"),
    ("timeout_s", 0), ("timeout_s", -5), ("timeout_s", True),
    ("timeout_s", float("nan")), ("timeout_s", float("inf")), ("timeout_s", "30"),
    ("timeout_s", None),
    ("api_key_env_var", ""), ("api_key_env_var", "   "), ("api_key_env_var", None),
    ("api_key_env_var", "9BAD"), ("api_key_env_var", "HAS SPACE"),
    ("api_key_env_var", "TODO(verify)"),
])
def test_invalid_config_fails_closed(field, value):
    with pytest.raises(SamConfigError):
        valid_config(**{field: value})


def test_missing_credential_causes_zero_calls():
    config = valid_config()
    session = RecordingSession()
    call = prepare_call(config, prompt="leaf", image_id="img-1", scope="s")
    with pytest.raises(SamConfigError, match="credential"):
        dispatch_call(session=session, config=config, call=call, environ={})
    with pytest.raises(SamConfigError, match="credential"):
        dispatch_call(session=session, config=config, call=call,
                      environ={"TEST_SAM_API_KEY": "   "})
    assert session.calls == []


def test_invalid_config_causes_zero_calls():
    session = RecordingSession()
    with pytest.raises(SamConfigError):
        dispatch_call(session=session, config="not-a-config",
                      call="not-a-call", environ={})
    assert session.calls == []
    config = valid_config()
    with pytest.raises(SamConfigError):
        dispatch_call(session=object(), config=config,
                      call=prepare_call(config, prompt="p", image_id="i", scope="s"),
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.calls == []


def test_credentials_excluded_everywhere():
    secret = "test-key-abc-123"
    config = valid_config()
    environ = {"TEST_SAM_API_KEY": secret}
    assert secret not in repr(config)
    call = prepare_call(config, prompt="leaf", image_id="img-1", scope="s")
    assert secret not in repr(call)
    assert secret not in json.dumps(dataclasses.asdict(call))
    session = RecordingSession()
    try:
        dispatch_call(session=session, config=config, call=call, environ={})
    except SamConfigError as exc:
        assert secret not in str(exc)
    assert resolve_api_key(config, environ) == secret


def test_session_receives_only_supported_metadata():
    config = valid_config()
    call = prepare_call(config, prompt="leaf", image_id="img-1", scope="s")
    session = RecordingSession(reply_text="ok")
    assert dispatch_call(session=session, config=config, call=call,
                         environ={"TEST_SAM_API_KEY": "k"}) == "ok"
    assert session.calls == [(
        SamOutboundCall(
            endpoint="https://sam.test.invalid/v1", timeout_s=30,
            model_id="test-sam-model", prompt="leaf", image_id="img-1", scope="s",
        ),
        "k",
    )]


def test_prepare_call_validates_fields():
    config = valid_config()
    for kwargs in ({"prompt": "", "image_id": "i", "scope": "s"},
                   {"prompt": "p", "image_id": "", "scope": "s"},
                   {"prompt": "p", "image_id": "i", "scope": ""},
                   {"prompt": "x" * 501, "image_id": "i", "scope": "s"}):
        with pytest.raises(SamConfigError):
            prepare_call(config, **kwargs)
    with pytest.raises(SamConfigError):
        prepare_call("not-a-config", prompt="p", image_id="i", scope="s")


def test_no_real_network_primitives():
    source = (Path(__file__).resolve().parents[1] / "src" / "mydrak" / "sam" / "client.py").read_text()
    for token in ("urllib", "http.client", "socket", "subprocess",
                  "requests", "httpx", "openai", "httpcore", "ssl"):
        assert token not in source


def test_default_transport_still_fake_and_mock_unchanged(tmp_path):
    from mydrak.sam.guard import LiveCampaignGuard
    from mydrak.sam.transport import FakeSamTransport, SamScanRequest
    assert isinstance(default_transport(), FakeSamTransport)
    guard = LiveCampaignGuard(campaign_id="client-check", state_dir=tmp_path)
    guard.authorize_campaign(approval_token="tok", scope="s")
    out = run_scan(
        guard=guard, transport=default_transport(),
        request=SamScanRequest(image_id="i", image_source_license="s",
                               prompt="p", scope="s"),
        expected_width=640, expected_height=480,
    )
    assert out.provenance == "synthetic-mock"
    assert out.frame.match_count == 0


CANONICAL_URL = "https://api.meta.ai/v1/responses"
PUBLIC_IMAGE = "https://example.test/leaf.jpg"
DATA_IMAGE = "data:image/png;base64,iVBORw0KGgo="


def live_config(**overrides):
    base = {
        "model_id": "sam-3.1",
        "endpoint": CANONICAL_URL,
        "timeout_s": 30,
        "api_key_env_var": "TEST_SAM_API_KEY",
    }
    base.update(overrides)
    return SamClientConfig(**base)


def live_call(config, prompt="green leaf"):
    return prepare_call(config, prompt=prompt, image_id="img-1", scope="s")


class RecordingHttpSession:
    """Test-only HTTP double. Records calls; performs no I/O."""

    def __init__(self, reply_text=""):
        self.posts = []
        self.reply_text = reply_text

    def post_http(self, *, url, headers, json_body, timeout_s):
        self.posts.append({
            "url": url, "headers": dict(headers),
            "json_body": json_body, "timeout_s": timeout_s,
        })
        return self.reply_text


def test_canonical_url_built_in_one_place():
    assert canonical_responses_url() == CANONICAL_URL
    assert canonical_responses_url() == SAM_API_BASE_URL + "/responses"


def test_exact_nested_body_with_public_url():
    assert serialize_sam_body(
        model_id="sam-3.1", prompt="green leaf", image_ref=PUBLIC_IMAGE,
    ) == {
        "model": "sam-3.1",
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "green leaf"},
                {"type": "input_image", "image_url": PUBLIC_IMAGE},
            ],
        }],
        "stream": False,
    }


def test_data_url_body_and_determinism():
    first = serialize_sam_body(
        model_id="sam-3.1", prompt="p", image_ref=DATA_IMAGE)
    assert first["input"][0]["content"][1] == {
        "type": "input_image", "image_url": DATA_IMAGE}
    second = serialize_sam_body(
        model_id="sam-3.1", prompt="p", image_ref=DATA_IMAGE)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize("image_ref", [
    "", "   ", None, 123, "notaurl", "ftp://host/img.png", "file:///img.png",
    "https://", "https://exa mple.test/i.png", "data:image/png,abc",
    "data:;base64,", "data:image/png;base64,", "data:image/png;base64:abc",
    "data:image/png;base64:ab c", "data:image/png;base64:ab!c",
])
def test_malformed_image_ref_rejected(image_ref):
    with pytest.raises(SamConfigError):
        serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=image_ref)


@pytest.mark.parametrize("kwargs", [
    {"model_id": "sam-3.1", "prompt": "", "image_ref": PUBLIC_IMAGE},
    {"model_id": "sam-3.1", "prompt": "p", "image_ref": ""},
    {"model_id": "sam-3.1", "prompt": "p", "image_ref": "   "},
    {"model_id": "", "prompt": "p", "image_ref": PUBLIC_IMAGE},
    {"model_id": "TODO(verify)", "prompt": "p", "image_ref": PUBLIC_IMAGE},
])
def test_missing_or_blank_body_inputs_rejected(kwargs):
    with pytest.raises(SamConfigError):
        serialize_sam_body(**kwargs)


def test_http_request_validates_method_url_body():
    config = live_config()
    good = build_http_request(config, live_call(config), image_ref=PUBLIC_IMAGE)
    assert (good.method, good.url, good.timeout_s) == ("POST", CANONICAL_URL, 30)
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="GET", url=CANONICAL_URL, timeout_s=30,
                       body=good.body)
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="POST", url="https://api.meta.ai/v1/other",
                       timeout_s=30, body=good.body)
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30, body={})


def test_build_rejects_mismatch_and_non_canonical():
    config = live_config()
    other = live_config(endpoint="https://api.meta.ai/v1/other")
    with pytest.raises(SamConfigError):
        build_http_request(config, live_call(other), image_ref=PUBLIC_IMAGE)
    with pytest.raises(SamConfigError, match="unexpected"):
        build_http_request(other, live_call(other), image_ref=PUBLIC_IMAGE)
    with pytest.raises(SamConfigError):
        build_http_request("not-a-config", live_call(config), image_ref=PUBLIC_IMAGE)


def test_dispatch_sends_exact_metadata_once():
    config = live_config()
    http_request = build_http_request(config, live_call(config), image_ref=PUBLIC_IMAGE)
    session = RecordingHttpSession(reply_text="raw-reply")
    assert dispatch_http(session=session, config=config, http_request=http_request,
                         environ={"TEST_SAM_API_KEY": "test-key-abc"}) == "raw-reply"
    assert session.posts == [{
        "url": CANONICAL_URL,
        "headers": {"Authorization": "Bearer test-key-abc",
                    "Content-Type": "application/json"},
        "json_body": http_request.body,
        "timeout_s": 30,
    }]


def test_dispatch_invalid_config_fails_before_session_call():
    config = live_config()
    http_request = build_http_request(config, live_call(config), image_ref=PUBLIC_IMAGE)
    session = RecordingHttpSession()
    with pytest.raises(SamConfigError):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={})
    with pytest.raises(SamConfigError):
        dispatch_http(session=object(), config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    with pytest.raises(SamConfigError):
        dispatch_http(session=session, config="bad", http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_credential_excluded_from_http_artifacts():
    secret = "test-key-xyz-789"
    config = live_config()
    http_request = build_http_request(config, live_call(config), image_ref=PUBLIC_IMAGE)
    assert secret not in repr(http_request)
    assert secret not in json.dumps(http_request.body)
    session = RecordingHttpSession()
    try:
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={})
    except SamConfigError as exc:
        assert secret not in str(exc)
        assert "TEST_SAM_API_KEY" not in str(exc)
    assert session.posts == []


def _good_http_request(config=None, image_ref=PUBLIC_IMAGE, prompt="green leaf"):
    config = config or live_config()
    return build_http_request(config, live_call(config, prompt=prompt), image_ref=image_ref)


def test_dispatch_revalidates_mutated_nested_body():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    http_request.body["input"][0]["content"][1]["image_url"] = "notaurl"
    with pytest.raises(SamConfigError):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_dispatch_rejects_unexpected_body_keys():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    http_request.body["surprise"] = 1
    with pytest.raises(SamConfigError, match="unexpected"):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []
    http_request.body.pop("surprise")
    http_request.body["input"][0]["content"][0]["extra"] = True
    with pytest.raises(SamConfigError, match="unexpected"):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_dispatch_rejects_config_mismatch():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    with pytest.raises(SamConfigError, match="must be sam-3.1"):
        dispatch_http(session=session, config=live_config(model_id="other-model"),
                      http_request=http_request, environ={"TEST_SAM_API_KEY": "k"})
    with pytest.raises(SamConfigError, match="does not match"):
        dispatch_http(session=session, config=live_config(timeout_s=31),
                      http_request=http_request, environ={"TEST_SAM_API_KEY": "k"})
    with pytest.raises(SamConfigError, match="unexpected"):
        dispatch_http(session=session,
                      config=live_config(endpoint="https://api.meta.ai/v1/other"),
                      http_request=http_request, environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_dispatch_passes_copy_not_stored_body():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    dispatch_http(session=session, config=config, http_request=http_request,
                  environ={"TEST_SAM_API_KEY": "k"})
    recorded = session.posts[0]["json_body"]
    assert recorded == http_request.body
    assert recorded is not http_request.body
    recorded["input"][0]["content"][1]["image_url"] = "notaurl"
    recorded["surprise"] = 1
    # The stored request is unaffected by session-side mutation.
    dispatch_http(session=session, config=config, http_request=http_request,
                  environ={"TEST_SAM_API_KEY": "k"})
    assert len(session.posts) == 2


def test_constructor_copies_and_validates_nested_body():
    config = live_config()
    raw = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    http_request = SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30, body=raw)
    raw["input"][0]["content"][0]["text"] = "changed-after-construction"
    assert http_request.body["input"][0]["content"][0]["text"] == "p"
    bad = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    bad["input"][0]["content"].append({"type": "input_text", "text": "x"})
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30, body=bad)
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30,
                       body={"model": "sam-3.1"})


class LeakingSession:
    """Injected double whose failure echoes everything it received."""

    def post_http(self, *, url, headers, json_body, timeout_s):
        raise RuntimeError(f"boom headers={headers} body={json_body}")


class ConfigErrorSession:
    def post_http(self, *, url, headers, json_body, timeout_s):
        raise SamConfigError(f"custom marker key={headers} body={json_body}")


def test_dispatch_session_exception_sanitized():
    config = live_config()
    prompt = "sanitize-me-prompt"
    http_request = _good_http_request(config, prompt=prompt)
    with pytest.raises(SamConfigError, match="^SAM session call failed$"):
        dispatch_http(session=LeakingSession(), config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "synth-key-9z"})
    try:
        dispatch_http(session=LeakingSession(), config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "synth-key-9z"})
    except SamConfigError as exc:
        assert "synth-key-9z" not in str(exc)
        assert prompt not in str(exc)
        assert PUBLIC_IMAGE not in str(exc)
        assert exc.__cause__ is None
    with pytest.raises(SamConfigError, match="^SAM session call failed$"):
        dispatch_http(session=ConfigErrorSession(), config=config,
                      http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "synth-key-9z"})
    try:
        dispatch_http(session=ConfigErrorSession(), config=config,
                      http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "synth-key-9z"})
    except SamConfigError as exc:
        assert "custom marker" not in str(exc)
        assert "synth-key-9z" not in str(exc)
        assert exc.__cause__ is None
        # Only the fixed public error renders; the session's message,
        # cause chain, and original traceback do not. (Standard frame
        # source lines are inherent to Python tracebacks and carry no
        # values, so the check targets the rendered exception only.)
        rendered = "".join(traceback.format_exception_only(exc))
        assert "SamConfigError: SAM session call failed" in rendered
        assert "custom marker" not in rendered
        assert "synth-key-9z" not in rendered
        assert prompt not in rendered


@pytest.mark.parametrize("image_ref", [
    "http://h.test/i.png",
    "https://h.test/i.png",
    "https://h.test:8443/i.png",
    "https://h.test/i.png?q=1#f",
    "https://h.test",
    "https://h.test./i.png",
    "HTTPS://h.test/i.png",
    "https://[::1]/i.png",
    "https://[::1]:443/i.png",
    "data:IMAGE/PNG;base64,QUJD",
    "data:image/svg+xml;base64,QUJD",
])
def test_strict_but_valid_image_refs_accepted(image_ref):
    body = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=image_ref)
    assert body["input"][0]["content"][1]["image_url"] == image_ref


@pytest.mark.parametrize("image_ref", [
    "https://user:pw@h.test/i.png",
    "https://user@h.test/i.png",
    "https://h.test:abc/i.png",
    "https://h.test:99999/i.png",
    "https://h.test:0/i.png",
    "https://h.test:/i.png",
    "https:///i.png",
    "https://:8080/i.png",
    "https://_bad/i.png",
    "https://h..test/i.png",
    "https://h.test:12x/i.png",
    "https://h.test:123456/i.png",
    "data:text/plain;base64,QUJD",
    "data:application/json;base64,QUJD",
    "data:video/mp4;base64,QUJD",
    "data:image;base64,QUJD",
    "data:image/png; charset=x;base64,QUJD",
])
def test_strict_image_refs_rejected(image_ref):
    with pytest.raises(SamConfigError):
        serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=image_ref)


@pytest.mark.parametrize("endpoint", [
    "https://user@h.test/v1",
    "https://user:pw@h.test/v1",
    "https://h.test:bad/v1",
    "https://h.test:99999/v1",
    "https:///v1",
    "https://:443/v1",
])
def test_strict_endpoints_rejected(endpoint):
    with pytest.raises(SamConfigError):
        valid_config(endpoint=endpoint)


def test_dispatch_rejects_valid_post_construction_mutation():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    # Shape-valid but different: the sent request must not change.
    http_request.body["input"][0]["content"][0]["text"] = "other valid prompt"
    with pytest.raises(SamConfigError, match="changed after construction"):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def _fake_secret():
    # Built from fragments so the full value never appears literally in
    # test source lines that could surface in formatted tracebacks.
    return "synth-secret-" + "9z4"


class ContextLeakSession:
    """Injected double raising RuntimeError echoing everything received."""

    def __init__(self, secret):
        self._secret = secret

    def post_http(self, *, url, headers, json_body, timeout_s):
        raise RuntimeError(
            f"marker secret={self._secret} headers={headers} body={json_body}")


class ContextLeakConfigSession:
    """Injected double raising SamConfigError echoing everything received."""

    def __init__(self, secret):
        self._secret = secret

    def post_http(self, *, url, headers, json_body, timeout_s):
        raise SamConfigError(
            f"marker secret={self._secret} headers={headers} body={json_body}")


@pytest.mark.parametrize("session_cls", [ContextLeakSession, ContextLeakConfigSession])
def test_dispatch_session_context_fully_severed(session_cls):
    fake = _fake_secret()
    config = live_config()
    prompt = "context-probe-prompt"
    http_request = _good_http_request(config, prompt=prompt)
    session = session_cls(fake)
    environ = {"TEST_SAM_API_KEY": fake}
    with pytest.raises(SamConfigError, match="^SAM session call failed$"):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ=environ)
    try:
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ=environ)
    except SamConfigError as exc:
        assert exc.__context__ is None
        assert exc.__cause__ is None
        assert fake not in str(exc)
        assert prompt not in str(exc)
        assert PUBLIC_IMAGE not in str(exc)
        rendered_only = "".join(traceback.format_exception_only(exc))
        assert "SamConfigError: SAM session call failed" in rendered_only
        assert fake not in rendered_only
        rendered_full = "".join(traceback.format_exception(exc))
        assert fake not in rendered_full
        assert prompt not in rendered_full


def test_body_read_access_preserved():
    http_request = _good_http_request()
    assert type(http_request.body) is dict
    assert http_request.body["model"] == "sam-3.1"
    assert set(http_request.body) == {"model", "input", "stream"}
    assert json.loads(json.dumps(http_request.body)) == http_request.body


@pytest.mark.parametrize("payload", ["QUI=", "TQ==", "QUJD", "iVBORw0KGgo="])
def test_strict_base64_payloads_accepted(payload):
    body = serialize_sam_body(
        model_id="sam-3.1", prompt="p",
        image_ref=f"data:image/png;base64,{payload}")
    assert body["input"][0]["content"][1]["image_url"].endswith(payload)


@pytest.mark.parametrize("payload", [
    "QUI", "QUJD=", "QUJD==", "AB=C", "A===", "====", "=ABC", "ABCDE",
])
def test_strict_base64_payloads_rejected(payload):
    with pytest.raises(SamConfigError):
        serialize_sam_body(
            model_id="sam-3.1", prompt="p",
            image_ref=f"data:image/png;base64,{payload}")


@pytest.mark.parametrize("image_ref", [
    "https://[2001:db8::1]/i.png",
    "https://[2001:db8::1]:8443/i.png",
    "https://[::ffff:192.0.2.1]/i.png",
])
def test_strict_ipv6_hosts_accepted(image_ref):
    body = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=image_ref)
    assert body["input"][0]["content"][1]["image_url"] == image_ref


@pytest.mark.parametrize("image_ref", [
    "https://[xyz]/i.png",
    "https://[]/i.png",
    "https://[12345::]/i.png",
    "https://[::1::2]/i.png",
    "https://[::ffff:999.1.1.1]/i.png",
    "https://[::1/i.png",
    "https://::1/i.png",
])
def test_strict_ipv6_hosts_rejected(image_ref):
    with pytest.raises(SamConfigError):
        serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=image_ref)


def test_message_type_message_accepted():
    config = live_config()
    raw = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    raw["input"][0]["type"] = "message"
    http_request = SamHttpRequest(
        method="POST", url=CANONICAL_URL, timeout_s=30, body=raw)
    session = RecordingHttpSession()
    dispatch_http(session=session, config=config, http_request=http_request,
                  environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts[0]["json_body"]["input"][0]["type"] == "message"


@pytest.mark.parametrize("type_value", ["response", "notification", "", None, 123])
def test_unsupported_message_types_rejected(type_value):
    raw = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    raw["input"][0]["type"] = type_value
    with pytest.raises(SamConfigError):
        SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30, body=raw)


def test_message_extra_key_still_unexpected():
    raw = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    raw["input"][0]["type"] = "message"
    raw["input"][0]["extra"] = 1
    with pytest.raises(SamConfigError, match="unexpected"):
        SamHttpRequest(method="POST", url=CANONICAL_URL, timeout_s=30, body=raw)


@pytest.mark.parametrize("model_id", ["other-model", "sam-3-1", "SAM-3.1", " sam-3.1"])
def test_serialize_rejects_non_documented_model(model_id):
    with pytest.raises(SamConfigError):
        serialize_sam_body(model_id=model_id, prompt="p", image_ref=PUBLIC_IMAGE)


def test_dispatch_rejects_non_documented_model_config():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    for model_id in ("other-model", "sam-3-1"):
        with pytest.raises(SamConfigError, match="must be sam-3.1"):
            dispatch_http(session=session, config=live_config(model_id=model_id),
                          http_request=http_request, environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_dispatch_rejects_hand_built_foreign_model_body():
    config = live_config()
    raw = serialize_sam_body(model_id="sam-3.1", prompt="p", image_ref=PUBLIC_IMAGE)
    raw["model"] = "other-model"
    foreign = SamHttpRequest(
        method="POST", url=CANONICAL_URL, timeout_s=30, body=raw)
    session = RecordingHttpSession()
    with pytest.raises(SamConfigError, match="does not match"):
        dispatch_http(session=session, config=config, http_request=foreign,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []


def test_dispatch_rejects_nested_valid_mutation():
    config = live_config()
    http_request = _good_http_request(config)
    session = RecordingHttpSession()
    # Shape-valid nested change: the image reference itself is swapped.
    http_request.body["input"][0]["content"][1]["image_url"] = (
        "https://other.test/leaf.jpg")
    with pytest.raises(SamConfigError, match="changed after construction"):
        dispatch_http(session=session, config=config, http_request=http_request,
                      environ={"TEST_SAM_API_KEY": "k"})
    assert session.posts == []

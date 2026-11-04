"""One guarded SAM request using a generated synthetic red-square JPEG."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import re
import time

from PIL import Image, ImageDraw

from mydrak.live.guard import DEFAULT_SPEND_LEDGER, add_live_arguments, load_live_provider_config
from mydrak.live.diagnostics import safe_condition_id
from mydrak.sam.guard import LiveCampaignGuard
from mydrak.sam.live_client import (
    DEFAULT_SAM_CAMPAIGN,
    DEFAULT_SAM_SCOPE,
    SamLiveClient,
    SamLiveError,
)

_ROOT = Path(__file__).resolve().parents[1]
_DIMENSIONS = (64, 64)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One guarded SAM 3.1 synthetic smoke request")
    add_live_arguments(parser)
    parser.add_argument("--show-structure", action="store_true")
    return parser


def synthetic_red_square() -> bytes:
    image = Image.new("RGB", _DIMENSIONS, "white")
    ImageDraw.Draw(image).rectangle((16, 16, 47, 47), fill="red")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()


def _structure_summary(text: str) -> str:
    try:
        value = json.loads(text)
        is_json = True
    except (TypeError, ValueError):
        value = text
        is_json = False
    top_type = type(value).__name__
    key_names: list[str] = []
    list_lengths: list[int] = []
    string_lengths: list[int] = []

    def visit(node) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if isinstance(key, str) and len(key) <= 64 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
                    key_names.append(key)
                visit(child)
        elif isinstance(node, list):
            list_lengths.append(len(node))
            for child in node:
                visit(child)
        elif isinstance(node, str):
            string_lengths.append(len(node))

    visit(value)
    return (
        f"STRUCTURAL is_json={str(is_json).lower()} top_level_type={top_type} "
        f"key_names={json.dumps(sorted(set(key_names)), separators=(',', ':'))} "
        f"list_lengths={json.dumps(list_lengths, separators=(',', ':'))} "
        f"string_lengths={json.dumps(string_lengths, separators=(',', ':'))}"
    )


def run(argv: list[str] | None = None, *, environ=None, output=print) -> int:
    args = build_parser().parse_args(argv)
    values = os.environ if environ is None else environ
    request_sent = False
    cost = "unknown"
    output_text: str | None = None
    guard_condition: str | None = None
    started = time.perf_counter()
    try:
        config = load_live_provider_config(_ROOT / "config/models.yaml", "sam")
        guard = LiveCampaignGuard(campaign_id=DEFAULT_SAM_CAMPAIGN)
        client = SamLiveClient(
            config, cli_authorized=args.live_authorized,
            max_spend_usd=args.max_spend_usd,
            ledger_path=str(_ROOT / DEFAULT_SPEND_LEDGER),
            environ=values, campaign_guard=guard,
        )
        result = client.send(
            prompt="red square", preprocessed_image=synthetic_red_square(),
            expected_width=_DIMENSIONS[0], expected_height=_DIMENSIONS[1],
            scope=DEFAULT_SAM_SCOPE,
        )
        request_sent = client.last_request_sent
        cost = str(result.estimated_cost_usd)
        output_text = result.output_text
        parse_ok = result.parse_ok
        status = "response_received"
        category = "none"
        code = 0
    except SamLiveError as exc:
        request_sent = bool(locals().get("client") and client.last_request_sent)
        if client.last_estimated_cost_usd is not None:
            cost = str(client.last_estimated_cost_usd)
        parse_ok = False
        status = "failed"
        category = exc.category
        if category == "guard_refused":
            guard_condition = safe_condition_id(exc.condition)
        code = 1
    except Exception:
        parse_ok = False
        status = "failed"
        category = "config_invalid"
        code = 1
    latency = max(0.0, (time.perf_counter() - started) * 1000)
    fields = [
        f"status={status}", f"request_sent={str(request_sent).lower()}",
        f"latency_ms={latency:.2f}", f"failure_category={category}",
    ]
    if category == "guard_refused":
        fields.append(f"guard_condition={safe_condition_id(guard_condition)}")
    fields.extend((
        f"estimated_cost_usd={cost}",
        f"streamed_chars={len(output_text) if output_text is not None else 0}",
        f"parse_ok={str(parse_ok).lower()}",
    ))
    output(" ".join(fields))
    if args.show_structure and output_text is not None:
        output(_structure_summary(output_text))
    return code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

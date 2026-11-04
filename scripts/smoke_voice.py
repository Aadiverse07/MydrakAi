"""One explicitly guarded, one-shot Muse Voice request; never run implicitly."""

from __future__ import annotations

import argparse
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys
import time
import wave

from mydrak.audio.client import VoiceClientError, VoiceTranscriptionClient
from mydrak.live.diagnostics import safe_condition_id
from mydrak.audio.convert import AudioConversionError, validate_wav
from mydrak.live.guard import DEFAULT_SPEND_LEDGER, add_live_arguments, load_live_provider_config

_ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="One guarded Muse Voice Transcribe request")
    add_live_arguments(value)
    value.add_argument("--wav", type=Path, help="user-owned WAV test recording")
    value.add_argument("--show-transcript", action="store_true")
    value.add_argument("--ledger", type=Path, default=_ROOT / DEFAULT_SPEND_LEDGER)
    return value


def synthetic_wav() -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 48000)
    return stream.getvalue()


def run(argv: list[str] | None = None, *, environ=None, output=print, stderr=None) -> int:
    args = parser().parse_args(argv)
    values = os.environ if environ is None else environ
    errors = sys.stderr if stderr is None else stderr
    request_sent = False
    category = "none"
    guard_condition: str | None = None
    status = "failed"
    cost = "unknown"
    seconds: float | None = None
    transcript = ""
    turns: int | None = None
    started = time.perf_counter()
    client = None
    try:
        config = load_live_provider_config(_ROOT / "config/models.yaml", "voice")
        if args.wav is None:
            audio = synthetic_wav()
        else:
            with args.wav.open("rb") as source:
                audio = source.read(config["max_input_bytes"] + 1)
        if len(audio) > config["max_input_bytes"]:
            raise AudioConversionError("input_too_large")
        info = validate_wav(
            audio, max_audio_seconds=config["max_audio_seconds"],
            max_upload_bytes=config["max_upload_bytes"],
            target_sample_rate=config["target_sample_rate"],
        )
        client = VoiceTranscriptionClient(
            config, cli_authorized=args.live_authorized,
            max_spend_usd=args.max_spend_usd,
            ledger_path=str(args.ledger), environ=values,
        )
        result = client.transcribe(audio)
        request_sent = client.last_request_sent
        cost = str(result.estimated_cost_usd)
        seconds = result.audio_seconds
        transcript = result.transcript
        turns = result.turns_count
        status = result.status
        category = "none"
    except AudioConversionError as exc:
        category = exc.category
        seconds = None
    except VoiceClientError as exc:
        request_sent = bool(client and client.last_request_sent)
        if client and client.last_estimated_cost_usd is not None:
            cost = str(client.last_estimated_cost_usd)
        category = exc.category
        if category == "guard_refused":
            guard_condition = safe_condition_id(exc.condition)
        seconds = locals().get("info").duration_seconds if locals().get("info") else None
    except Exception:
        category = "config_invalid"
    latency = max(0.0, (time.perf_counter() - started) * 1000)
    fields = [
        f"status={status}", f"request_sent={str(request_sent).lower()}",
        f"latency_ms={latency:.2f}", f"failure_category={category}",
    ]
    if category == "guard_refused":
        fields.append(f"guard_condition={safe_condition_id(guard_condition)}")
    fields.extend((
        f"estimated_cost_usd={cost}",
        f"audio_seconds={seconds if seconds is not None else 'unknown'}",
        f"transcript_chars={len(transcript)}",
        f"turns_count={turns if turns is not None else 'unknown'}",
    ))
    output(" ".join(fields))
    if args.show_transcript and status == "response_received":
        print("WARNING: transcript output is only for non-farmer test audio.", file=errors)
        output("transcript=" + json.dumps(transcript, ensure_ascii=False))
    return 0 if status in {"response_received", "empty_transcript"} else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

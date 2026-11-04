"""Bounded temporary-file ffmpeg conversion and stdlib WAV validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable
import wave


class AudioConversionError(ValueError):
    """Typed, value-free failure from local conversion or WAV validation."""

    def __init__(self, category: str) -> None:
        super().__init__("audio conversion or validation failed")
        self.category = category


@dataclass(frozen=True)
class WavInfo:
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_width_bytes: int
    frames: int


def validate_wav(
    audio: bytes,
    *,
    max_audio_seconds: int,
    max_upload_bytes: int,
    target_sample_rate: int = 24000,
) -> WavInfo:
    if not isinstance(audio, bytes) or not audio:
        raise AudioConversionError("wav_invalid")
    if type(max_upload_bytes) is not int or max_upload_bytes < 1 or len(audio) > max_upload_bytes:
        raise AudioConversionError("upload_too_large")
    if type(max_audio_seconds) is not int or max_audio_seconds < 1:
        raise AudioConversionError("config_invalid")
    if type(target_sample_rate) is not int or target_sample_rate < 1:
        raise AudioConversionError("config_invalid")
    try:
        with wave.open(BytesIO(audio), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
    except (wave.Error, EOFError, OSError):
        raise AudioConversionError("wav_invalid") from None
    duration = frames / rate if rate > 0 else 0.0
    if channels != 1 or sample_width != 2 or rate != target_sample_rate or frames < 1:
        raise AudioConversionError("wav_invalid")
    if duration <= 0 or duration > max_audio_seconds:
        raise AudioConversionError("duration_invalid")
    return WavInfo(duration, rate, channels, sample_width, frames)


def convert_audio(
    audio: bytes,
    *,
    max_input_bytes: int,
    max_upload_bytes: int,
    max_audio_seconds: int,
    target_sample_rate: int = 24000,
    ffmpeg_path: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
    timeout_s: float = 30.0,
) -> tuple[bytes, WavInfo]:
    """Convert arbitrary ffmpeg-readable bytes to validated mono PCM WAV.

    Both temporary files are confined to a TemporaryDirectory and removed on
    success or failure. Tests inject ``runner`` and never execute ffmpeg.
    """
    if not isinstance(audio, bytes) or not audio:
        raise AudioConversionError("input_invalid")
    if type(max_input_bytes) is not int or max_input_bytes < 1:
        raise AudioConversionError("config_invalid")
    if (
        type(max_upload_bytes) is not int or max_upload_bytes < 1
        or type(max_audio_seconds) is not int or max_audio_seconds < 1
        or type(target_sample_rate) is not int or target_sample_rate < 1
    ):
        raise AudioConversionError("config_invalid")
    if len(audio) > max_input_bytes:
        raise AudioConversionError("input_too_large")
    executable = ffmpeg_path or shutil.which("ffmpeg")
    if not executable:
        raise AudioConversionError("ffmpeg_missing")
    if not callable(runner) or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise AudioConversionError("config_invalid")
    try:
        with tempfile.TemporaryDirectory(prefix="mydrak-audio-") as directory:
            source = Path(directory) / "input.bin"
            target = Path(directory) / "output.wav"
            source.write_bytes(audio)
            command = [
                executable, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(source), "-ac", "1", "-ar", str(target_sample_rate),
                "-c:a", "pcm_s16le", "-map_metadata", "-1", str(target),
            ]
            try:
                completed = runner(
                    command, capture_output=True, timeout=timeout_s,
                    check=False, shell=False,
                )
            except subprocess.TimeoutExpired:
                raise AudioConversionError("ffmpeg_timeout") from None
            except Exception:
                raise AudioConversionError("conversion_failed") from None
            if getattr(completed, "returncode", 1) != 0 or not target.is_file():
                raise AudioConversionError("conversion_failed")
            converted = target.read_bytes()
            info = validate_wav(
                converted, max_audio_seconds=max_audio_seconds,
                max_upload_bytes=max_upload_bytes,
                target_sample_rate=target_sample_rate,
            )
            return converted, info
    except AudioConversionError:
        raise
    except (OSError, ValueError):
        raise AudioConversionError("conversion_failed") from None

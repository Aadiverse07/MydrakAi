"""Deterministic, explicitly labeled providers for the offline demo path."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Protocol

from mydrak.vision.diagnosis import DiagnosisProvider
from mydrak.vision.preprocessing import PreprocessedImage

SYNTHETIC_MOCK_LABEL = "SYNTHETIC / MOCK"


class SyntheticSamProvider(Protocol):
    provenance: str

    def generate(self, image: PreprocessedImage) -> Mapping[str, object]: ...


@dataclass
class DeterministicMockDiagnosisProvider:
    """Queue validated-schema-shaped JSON values; never performs I/O."""

    outputs: Sequence[object]
    repair_output: object | None = None
    fail_calls: frozenset[int] = frozenset()
    timeout_calls: frozenset[int] = frozenset()
    provenance: str = field(default=SYNTHETIC_MOCK_LABEL, init=False)
    generate_calls: int = field(default=0, init=False)
    repair_calls: int = field(default=0, init=False)
    bound_image_hash: str | None = field(default=None, init=False)

    def bind_image(self, image_hash: str) -> None:
        """Associate this predetermined fixture queue with one normalized photo."""
        if not isinstance(image_hash, str) or len(image_hash) != 64:
            raise ValueError("mock image hash is invalid")
        self.bound_image_hash = image_hash

    def generate(self) -> object:
        index = self.generate_calls
        self.generate_calls += 1
        if index in self.timeout_calls:
            raise TimeoutError("synthetic mock provider timeout")
        if index in self.fail_calls:
            raise RuntimeError("synthetic mock provider unavailable")
        if index >= len(self.outputs):
            return None
        value = self.outputs[index]
        if isinstance(value, Mapping):
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        return value

    def repair(self, invalid_output: str) -> object:
        self.repair_calls += 1
        value = self.repair_output
        if isinstance(value, Mapping):
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        return value


@dataclass(frozen=True)
class MockSamResponse:
    payload: Mapping[str, object] = field(repr=False)
    provenance: str = SYNTHETIC_MOCK_LABEL


@dataclass
class DeterministicMockSamProvider:
    """Build the local synthetic-grid grammar for the supplied image size."""

    leaf_rows: tuple[str, ...]
    lesion_rows: tuple[str, ...]
    fail: bool = False
    provenance: str = field(default=SYNTHETIC_MOCK_LABEL, init=False)
    generate_calls: int = field(default=0, init=False)

    def generate(self, image: PreprocessedImage) -> MockSamResponse:
        self.generate_calls += 1
        if self.fail:
            raise RuntimeError("synthetic mock SAM unavailable")
        payload = {
            "image": {"width": image.width, "height": image.height},
            "objects": [
                self._object("leaf", self.leaf_rows, image.width, image.height),
                self._object("lesion", self.lesion_rows, image.width, image.height),
            ],
        }
        return MockSamResponse(deepcopy(payload))

    @staticmethod
    def _object(
        object_id: str, rows: tuple[str, ...], frame_width: int, frame_height: int
    ) -> dict[str, object]:
        width = len(rows[0]) if rows else 0
        return {
            "id": object_id,
            "box": [0, 0, frame_width, frame_height],
            "mask": {
                "width": width,
                "height": len(rows),
                "encoding": "synthetic-grid-v1",
                "data": "\n".join(rows),
            },
        }


@dataclass
class DeterministicMockTranscriber:
    """Failure-injection-only transcription boundary; never reads audio bytes."""

    fail: bool = True
    provenance: str = field(default=SYNTHETIC_MOCK_LABEL, init=False)
    calls: int = field(default=0, init=False)

    def transcribe(self) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic mock transcription failure")
        return "SYNTHETIC_TRANSCRIPT"

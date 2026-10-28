"""Offline image-plus-segmentation workflow (Phase 2, Task 3).

Data flow, each step reusing existing validation (nothing reimplemented):

1. ``read_local_image`` validates a real local file header into an
   ``IntakeImage`` descriptor (format, dimensions, byte size).
2. ``parse_sam_output`` validates an explicitly supplied, controlled
   segmentation fixture into a ``SamSegmentation``.
3. Both are returned side by side with explicit provenance labels.

Provenance contract (load-bearing): ``image`` is VALIDATED LOCAL METADATA
established by reading the file; ``segmentation`` is SUPPLIED FIXTURE DATA
established only by parsing the caller's document. A successful run does NOT
mean SAM processed the image, and nothing here is a diagnosis. The
segmentation fixture frame is independent input; it is not cross-checked
against the image file.

Failures propagate as the readers' own controlled errors (``IntakeError``,
``SamOutputError``): no paths, OS text, or raw bytes escape. The workflow
opens the image file exactly once (inside the reader) and never transmits
anything anywhere.
"""

import os
import time
import uuid
from typing import Any

from mydrak.intake.adapter import IntakeImage
from mydrak.sam.output import SamLimits, SamSegmentation, parse_sam_output
from mydrak.vision.source import read_local_image

IMAGE_PROVENANCE = "validated_local_metadata"
SEGMENTATION_PROVENANCE = "supplied_fixture"


class OfflineResult:
    """Structured outcome of one offline image-plus-segmentation run."""

    __slots__ = ("request_id", "image", "segmentation", "stages", "total_duration_ms")

    def __init__(
        self,
        request_id: str,
        image: IntakeImage,
        segmentation: SamSegmentation,
        stages: list[dict[str, Any]],
        total_duration_ms: float,
    ) -> None:
        self.request_id = request_id
        self.image = image
        self.segmentation = segmentation
        self.stages = [dict(stage) for stage in stages]
        self.total_duration_ms = total_duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "image": {
                "provenance": IMAGE_PROVENANCE,
                "format": self.image.format,
                "width": self.image.width,
                "height": self.image.height,
                "size_bytes": self.image.size_bytes,
            },
            "segmentation": {
                "provenance": SEGMENTATION_PROVENANCE,
                "image_width": self.segmentation.image_width,
                "image_height": self.segmentation.image_height,
                "match_count": self.segmentation.match_count,
                "objects": [
                    {
                        "id": obj.id,
                        "box": list(obj.box),
                        "mask": {
                            "width": obj.mask.width,
                            "height": obj.mask.height,
                            "encoding": obj.mask.encoding,
                            "data": obj.mask.data,
                        },
                        "score": obj.score,
                    }
                    for obj in self.segmentation.objects
                ],
            },
            "stages": [dict(stage) for stage in self.stages],
            "total_duration_ms": self.total_duration_ms,
        }


def run_offline_image_workflow(
    image_path: str | os.PathLike[str],
    segmentation_document: Any,
    *,
    limits: SamLimits | None = None,
) -> OfflineResult:
    """Run the offline workflow: read image header, parse supplied fixture."""
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    stages: list[dict[str, Any]] = []

    step_started = time.perf_counter()
    image = read_local_image(image_path)
    stages.append({
        "stage": "inspect_image",
        "outcome": "ok",
        "duration_ms": round((time.perf_counter() - step_started) * 1000, 3),
    })

    step_started = time.perf_counter()
    segmentation = parse_sam_output(segmentation_document, limits)
    stages.append({
        "stage": "parse_segmentation",
        "outcome": "ok",
        "duration_ms": round((time.perf_counter() - step_started) * 1000, 3),
    })

    return OfflineResult(
        request_id=request_id,
        image=image,
        segmentation=segmentation,
        stages=stages,
        total_duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )

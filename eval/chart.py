"""Small dependency-free SVG charts for offline evaluation reports."""

from __future__ import annotations

from html import escape
from typing import Any

def cost_accuracy_svg(metrics: dict[str, dict[str, Any]], records: list[dict[str, Any]]) -> str:
    """Render cost/task versus all-case accuracy; unknown cost is never plotted as zero."""
    synthetic = _is_synthetic(records)
    width, height = 720, 440
    known = [item for item in metrics.values() if item["cost_per_task_usd"] is not None]
    xmax = max((item["cost_per_task_usd"] for item in known), default=1.0) or 1.0
    parts = [_svg_start(width, height, "Cost per task and accuracy")]
    parts.append(_banner(synthetic))
    parts.extend([
        '<text x="360" y="62" text-anchor="middle" font-size="20">Cost per task vs accuracy</text>',
        '<line x1="85" y1="360" x2="660" y2="360" stroke="#333"/>',
        '<line x1="85" y1="100" x2="85" y2="360" stroke="#333"/>',
        '<text x="370" y="410" text-anchor="middle">Cost per task (USD)</text>',
        '<text transform="translate(25 230) rotate(-90)" text-anchor="middle">Accuracy over all cases</text>',
    ])
    for strategy, item in sorted(metrics.items()):
        name = escape(strategy)
        accuracy = item["accuracy_all"]
        if item["cost_per_task_usd"] is None:
            parts.append(f'<text x="105" y="{125 + 26 * list(sorted(metrics)).index(strategy)}" fill="#9a3412">{name}: cost unknown</text>')
        else:
            x = 85 + 575 * item["cost_per_task_usd"] / xmax
            y = 360 - 260 * (accuracy or 0.0)
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="#2563eb"/>')
            parts.append(f'<text x="{x + 10:.2f}" y="{y - 8:.2f}">{name}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def accuracy_coverage_svg(curves: dict[str, list[dict[str, Any]]], records: list[dict[str, Any]]) -> str:
    """Render recorded-score curves without selecting or implying a threshold."""
    width, height = 720, 440
    parts = [_svg_start(width, height, "Accuracy versus coverage")]
    parts.append(_banner(_is_synthetic(records)))
    parts.extend([
        '<text x="360" y="62" text-anchor="middle" font-size="20">Accuracy vs coverage (recorded scores)</text>',
        '<line x1="85" y1="360" x2="660" y2="360" stroke="#333"/>',
        '<line x1="85" y1="100" x2="85" y2="360" stroke="#333"/>',
        '<text x="370" y="410" text-anchor="middle">Coverage</text>',
        '<text transform="translate(25 230) rotate(-90)" text-anchor="middle">Accuracy</text>',
    ])
    palette = ("#2563eb", "#15803d", "#c2410c", "#7e22ce", "#0891b2")
    for index, (strategy, curve) in enumerate(sorted(curves.items())):
        points = []
        for point in curve:
            if point["accuracy"] is None:
                continue
            x = 85 + 575 * point["coverage"]
            y = 360 - 260 * point["accuracy"]
            points.append(f"{x:.2f},{y:.2f}")
        if points:
            parts.append(f'<polyline fill="none" stroke="{palette[index % len(palette)]}" points="{" ".join(points)}"/>')
            parts.append(f'<text x="{95 + index * 120}" y="92" fill="{palette[index % len(palette)]}">{escape(strategy)}</text>')
    if not any(curves.values()):
        parts.append('<text x="360" y="230" text-anchor="middle">No recorded scores</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_start(width: int, height: int, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">')


def _banner(synthetic: bool) -> str:
    return ('<rect x="0" y="0" width="720" height="30" fill="#7f1d1d"/>'
            '<text x="360" y="21" text-anchor="middle" fill="white" font-weight="bold">SYNTHETIC FIXTURE</text>') if synthetic else ""


def _is_synthetic(records: list[dict[str, Any]]) -> bool:
    return any(str(row.get("provenance", "")).lower().startswith("synthetic") for row in records)

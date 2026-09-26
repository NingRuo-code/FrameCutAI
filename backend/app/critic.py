import re
from typing import Any


EVIDENCE_PATTERN = re.compile(
    r"\[Evidence:\s+(?P<segment_id>segment-\d+)\s+@\s+"
    r"(?P<start>\d+)s-(?P<end>\d+)s\]"
)


def make_warning(code: str, message: str, severity: str = "warning") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def critique_document(context: dict[str, Any], markdown: str) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    segments = {segment["segment_id"]: segment for segment in context.get("segments", [])}
    evidence_items = context.get("evidence", [])

    for evidence in evidence_items:
        expected_label = (
            f"[Evidence: {evidence['segment_id']} @ "
            f"{evidence['start_seconds']}s-{evidence['end_seconds']}s]"
        )
        if expected_label not in markdown:
            warnings.append(
                make_warning(
                    "missing-evidence-label",
                    f"Missing timestamped Evidence label for {evidence['segment_id']}.",
                )
            )

    for match in EVIDENCE_PATTERN.finditer(markdown):
        segment_id = match.group("segment_id")
        start = int(match.group("start"))
        end = int(match.group("end"))
        segment = segments.get(segment_id)
        if segment is None:
            warnings.append(
                make_warning(
                    "invalid-evidence-segment",
                    f"Evidence references unknown Segment {segment_id}.",
                )
            )
            continue

        if start != segment["start_seconds"] or end != segment["end_seconds"]:
            warnings.append(
                make_warning(
                    "invalid-evidence-time",
                    f"Evidence timestamp for {segment_id} does not match VideoContext.",
                )
            )

    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if stripped.startswith("- Score source:"):
            continue
        if stripped.startswith("- OCR:") or stripped.startswith("- Vision:"):
            continue
        if stripped.startswith("- Segment:") or stripped.startswith("- Timestamp:"):
            continue
        if stripped.startswith("- Transcript:") or stripped.startswith("- Frames:"):
            continue
        if stripped.startswith("- Visual summary:"):
            continue
        if stripped.startswith("- VideoContext") or stripped.startswith("- Selective vision"):
            continue
        if stripped.startswith("- Provider calls"):
            continue
        if "[Evidence:" not in stripped and (
            "guarantee" in stripped.lower()
            or "perfect" in stripped.lower()
            or "always" in stripped.lower()
        ):
            warnings.append(
                make_warning(
                    "unsupported-claim",
                    f"Potential unsupported claim lacks Evidence: {stripped[2:]}",
                )
            )

    for segment in segments.values():
        score = segment.get("score", {})
        is_high_value_visual = (
            segment.get("selected_for_vision")
            or score.get("visual_dependency", 0) >= 0.55
        )
        if not is_high_value_visual:
            continue

        frame_ids = [frame["frame_id"] for frame in segment.get("frames", [])]
        if segment["segment_id"] not in markdown and not any(
            frame_id in markdown for frame_id in frame_ids
        ):
            warnings.append(
                make_warning(
                    "missing-high-value-visual",
                    f"High-value visual Segment {segment['segment_id']} is not used in the document.",
                )
            )

    return {
        "status": "passed" if not warnings else "warning",
        "warning_count": len(warnings),
        "warnings": warnings,
    }

"""Regression tests for video detection deduplication.

These are intentionally pure-Python (no DB) and focus on ensuring that
per-frame differences don't cause loss of important fields when detections
are deduplicated.
"""

import asyncio


def _run(coro):
    """Run an async coroutine without requiring pytest-asyncio."""
    return asyncio.run(coro)


def test_video_dedupe_preserves_unit_bbox_taxonomy_hints():
    from app.api.routes.video_scanning import deduplicate_detections

    detections = [
        {
            "canonical_name": "rice",
            "detected_name": "Rice",
            "confidence": 0.90,
            "quantity": 1,
            "quantity_confidence": 0.10,
            # missing unit/bbox/taxonomy on the highest-confidence frame
        },
        {
            "canonical_name": "rice",
            "detected_name": "Rice",
            "confidence": 0.80,
            "quantity": 2,
            "unit": "kg",
            "quantity_confidence": 0.90,
            "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
            "category": "grain",
            "subcategory": "rice",
            "cuisine": "indian",
        },
    ]

    out = _run(deduplicate_detections(detections))

    assert len(out) == 1
    d = out[0]

    # Should keep the best available quantity/unit info, not drop unit.
    assert d.get("unit") == "kg"
    assert d.get("quantity") == 2
    assert d.get("quantity_confidence") == 0.90

    # Should preserve bbox/taxonomy hints from any frame.
    assert isinstance(d.get("bbox"), dict)
    assert d["bbox"].get("width") == 0.3
    assert d.get("category") == "grain"
    assert d.get("subcategory") == "rice"
    assert d.get("cuisine") == "indian"


def test_video_dedupe_weighted_average_quantity_same_unit():
    from app.api.routes.video_scanning import deduplicate_detections

    detections = [
        {
            "canonical_name": "milk",
            "confidence": 0.70,
            "quantity": 1,
            "unit": "l",
            "quantity_confidence": 0.20,
        },
        {
            "canonical_name": "milk",
            "confidence": 0.60,
            "quantity": 3,
            "unit": "l",
            "quantity_confidence": 0.80,
        },
    ]

    out = _run(deduplicate_detections(detections))

    assert len(out) == 1
    d = out[0]

    # Weighted average by quantity_confidence: (1*0.2 + 3*0.8) / 1.0 = 2.6
    assert d.get("unit") == "l"
    assert abs(float(d.get("quantity")) - 2.6) < 1e-6
    assert d.get("quantity_confidence") == 0.80

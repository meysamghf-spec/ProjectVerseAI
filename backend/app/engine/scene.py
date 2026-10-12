"""Conceptual scene parameters derived from project quantities.

The geometry is a visualization rule, not an architectural model. Dimensions
that the user did not state are returned alongside the assumption that produced them.
"""

from __future__ import annotations

import math


def construction_scene(gfa: float, floors: int, basements: int, assumptions: dict | None = None) -> dict:
    assumptions = assumptions or {}
    floors = max(int(floors), 1)
    basements = max(int(basements), 0)
    floor_height = float(assumptions.get("floor_to_floor_height_m") or 3.2)
    basement_height = float(assumptions.get("basement_height_m") or 3.0)
    aspect = float(assumptions.get("aspect_ratio") or 1.5)
    footprint = float(gfa) / floors
    width = math.sqrt(footprint / aspect)
    length = width * aspect
    core_width = max(6.0, width * 0.22)
    core_length = max(8.0, length * 0.28)
    if core_width > width * 0.6:
        core_width = width * 0.45
    if core_length > length * 0.6:
        core_length = length * 0.45
    return {
        "metaphor": "procedural-building",
        "label": "Conceptual construction massing",
        "disclaimer": (
            "Procedural massing for planning review. It is not an architectural, "
            "structural, or code-compliant building model."
        ),
        "floors": floors,
        "basements": basements,
        "gfa_sqm": float(gfa),
        "footprint_sqm": round(footprint, 2),
        "floor_height_m": floor_height,
        "basement_height_m": basement_height,
        "width_m": round(width, 2),
        "length_m": round(length, 2),
        "core_width_m": round(core_width, 2),
        "core_length_m": round(core_length, 2),
        "column_spacing_m": 8.0,
        "rules": [
            "Above-ground gross floor area is divided equally across floors to estimate the footprint.",
            "Length is width multiplied by the aspect-ratio assumption.",
            "Cores, columns, and envelopes are simplified boxes tied to construction phases.",
            "Basement volumes sit below the ground plane and map to the basement task.",
        ],
    }


def generic_scene(project_type: str, phases: list[str]) -> dict:
    metaphors = {
        "software": "system-modules",
        "manufacturing": "production-line",
        "infrastructure": "linear-alignment",
        "urban": "district-blocks",
        "logistics": "distribution-network",
        "research": "research-layers",
        "event": "venue-zones",
        "custom": "phase-blocks",
    }
    return {
        "metaphor": metaphors.get(project_type, "phase-blocks"),
        "label": f"Conceptual {project_type.replace('_', ' ')} diagram",
        "disclaimer": (
            "This is a labeled conceptual diagram of plan entities. "
            "It is not a measured site, system architecture, or engineering drawing."
        ),
        "phases": phases,
        "rules": [
            "Each major object maps to a task or phase id from the generated plan.",
            "Position encodes sequence or flow, not geographic coordinates, unless a location was modeled.",
        ],
    }

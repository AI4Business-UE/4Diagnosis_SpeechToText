"""Canonical categories and fields used by reviewed NER references."""

NER_FIELD_TYPES = {
    "patient": {"first_name": str, "last_name": str, "pesel": str, "age": int},
    "components": {
        "name": str, "count": int, "dim_x": (int, float), "dim_y": (int, float),
        "dim_z": (int, float), "length": (int, float), "diameter": (int, float),
        "unit": str, "description": str,
    },
    "lesions": {
        "type": str, "dim_x": (int, float), "dim_y": (int, float), "dim_z": (int, float),
        "diameter": (int, float), "length": (int, float), "unit": str, "color": str,
        "structure": str, "features": list, "infiltration": str, "location_description": str,
        "organ": str, "shape": str, "borders": str, "additional_notes": str,
        "component_index": int,
    },
    "fluid_samples": {
        "source": str, "material_type": str, "volume_ml": (int, float), "color": str,
        "clarity": str, "consistency": str, "fixation": str,
    },
}

NER_CATEGORIES = tuple(NER_FIELD_TYPES)
NER_ENTITY_FIELDS = {category: set(fields) for category, fields in NER_FIELD_TYPES.items()}
NER_MEASUREMENT_FIELDS = frozenset({"dim_x", "dim_y", "dim_z", "length", "diameter"})

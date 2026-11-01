"""Canonical categories and fields used by reviewed NER references."""

NER_CATEGORIES = ("patient", "components", "lesions", "fluid_samples")

NER_ENTITY_FIELDS = {
    "patient": {"first_name", "last_name", "pesel", "age"},
    "components": {"name", "count", "dim_x", "dim_y", "dim_z", "length", "diameter", "unit", "description"},
    "lesions": {
        "type", "dim_x", "dim_y", "dim_z", "diameter", "length", "unit", "color", "structure",
        "features", "infiltration", "location_description", "organ", "shape", "borders",
        "additional_notes", "component_index",
    },
    "fluid_samples": {"source", "material_type", "volume_ml", "color", "clarity", "consistency", "fixation"},
}

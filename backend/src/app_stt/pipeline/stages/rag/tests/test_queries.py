from typing import Literal
from collections import Counter

import pytest

from app_stt.pipeline.stages.ner.entities import Lesion, Component, FluidSample, LesionExtraction, ComponentExtraction, FluidSampleExtraction
from ..qdrant.queries import build_queries

def create_component(name: str, count: int | None = None) -> Component:
    return Component(name=name, count=count)

def create_lesion(type: Literal["guz", "torbiel", "polip", "ognisko", "zmiana"]) -> Lesion:
    return Lesion(type=type)

def create_fluid(source: str, material_type: str | None = None):
    return FluidSample(source=source, material_type=material_type)

@pytest.fixture
def component_extraction():
    return [Component(**c) for c in [
        {
            "name": "materiał",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "unit": "cm"
        }
    ]]
    
@pytest.fixture
def component_extraction_multiple():
    return [Component(**c) for c in [
        {
            "name": "materiał",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "unit": "cm"
        },
        {
            "name": "nerka"
        }
    ]]

@pytest.fixture
def lesion_extraction():
    return [Lesion(**l) for l in [
        {
            "type": "guz",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 0
        },
        {
            "type": "guz",
            "dim_x": 3.5,
            "dim_y": 3.0,
            "dim_z": 3.5,
            "color": "żółtej",
            "features": [
                "wylewy_krwawe"
            ],
            "component_index": 0
        }
    ]]

@pytest.fixture
def lesion_extraction_multiple_lesions_for_single_component():
    """
    To test output for many lesions with the same 'component_index',
    with few additional lesions with different 'organ' fields set.
    """
    return [Lesion(**l) for l in [
        {
            "type": "guz",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 0
        },
        {
            "type": "guz",
            "dim_x": 3.5,
            "dim_y": 3.0,
            "dim_z": 3.5,
            "color": "żółtej",
            "features": [
                "wylewy_krwawe"
            ],
            "component_index": 0
        },
        {
            "type": "torbiel",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 0
        },
        {
            "type": "ognisko",
            "component_index": 0
        },
        {
            "type": "zmiana",
            "organ": "jądro"
        },
        {
            "type": "zmiana",
            "organ": "nerka"
        }
    ]]

@pytest.fixture
def lesion_extraction_for_multiple_components():
    """
    For testing output with many lesions with different 'component_index' values.
    """ 
    return [Lesion(**l) for l in [
        {
            "type": "guz",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 0
        },
        {
            "type": "guz",
            "dim_x": 3.5,
            "dim_y": 3.0,
            "dim_z": 3.5,
            "color": "żółtej",
            "features": [
                "wylewy_krwawe"
            ],
            "component_index": 0
        },
        {
            "type": "torbiel",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 1
        },
        {
            "type": "ognisko",
            "component_index": 1
        },
        {
            "type": "zmiana",
            "organ": "jądro"
        },
        {
            "type": "zmiana",
            "organ": "nerka"
        }
    ]]
 
@pytest.fixture
def fluid_extraction():
    return [FluidSample(**f) for f in [
        {
          "source": "z torbieli",
          "material_type": "płyn",
          "volume_ml": None,
          "color": None,
          "clarity": "klarowny",
          "consistency": None,
          "fixation": None
        }
    ]]
 
def test_query_building(component_extraction, lesion_extraction, fluid_extraction):
    queries = build_queries(component_extraction, lesion_extraction, fluid_extraction)
     
    assert len(queries) > 0
    
def test_query_building_fluid_only(fluid_extraction):
    components = []
    lesions = []
    queries = build_queries(components, lesions, fluid_extraction)
    
    fluid_sample = fluid_extraction[0]
    
    assert len(queries) == 2    
    assert queries[0].using == 'dense'
    assert fluid_sample.source in queries[0].text
    assert fluid_sample.material_type in queries[0].text
    assert queries[1].using == 'sparse'
    assert fluid_sample.source in queries[1].text
    assert fluid_sample.material_type in queries[1].text
    
def test_query_building_all(component_extraction, lesion_extraction, fluid_extraction):
    queries = build_queries(component_extraction, lesion_extraction, fluid_extraction)
    
    dense_parts = []
    sparse_parts = []
    dense_parts.append(component_extraction[0].name)
    sparse_parts.append(component_extraction[0].name)
    
    dense_parts.append('płyn pochodzenia ' + fluid_extraction[0].source)
    sparse_parts.append('płyn ' + fluid_extraction[0].source)
    
    dense_parts.append(fluid_extraction[0].material_type)
    sparse_parts.append(fluid_extraction[0].material_type)
    
    dense_parts.append(f'2 {lesion_extraction[0].type}')
    sparse_parts.append(lesion_extraction[0].type)
    
    assert len(queries) == 3
    assert queries[0].using == 'dense'
    assert queries[1].using == 'sparse'
    assert queries[2].using == 'dense'
        
    assert dense_parts == queries[0].text.split(', ')
    assert ' '.join(sparse_parts) == queries[1].text
    assert f"Na przekrojach {sparse_parts[0]} obecne 2 {sparse_parts[-1]}" == queries[2].text
    
def test_query_building_multiple_lession(component_extraction, lesion_extraction_multiple_lesions_for_single_component):
    queries = build_queries(component_extraction, lesion_extraction_multiple_lesions_for_single_component, [])
    
    lesions = lesion_extraction_multiple_lesions_for_single_component
    
    assert len(queries) == 4
    assert (f"Na przekrojach {component_extraction[0].name} obecne 2 {lesions[0].type},"
    f" {lesions[2].type}, {lesions[3].type}") == queries[2].text
    assert (f"Na przekrojach w obrębie {lesions[4].organ} {lesions[4].type}"
    f", ponadto w obrębie {lesions[5].organ} {lesions[5].type}") == queries[3].text
    
def test_query_building_multiple_lesions_for_diffrent_components(component_extraction_multiple, lesion_extraction_for_multiple_components):
    fluid_extraction = []
    queries = build_queries(component_extraction_multiple, lesion_extraction_for_multiple_components, fluid_extraction)
    
    components = component_extraction_multiple
    
    first_comp_lesions = [l.type for l in lesion_extraction_for_multiple_components if l.component_index == 0]
    first_lesion_counts = Counter(first_comp_lesions)
    first_comp_lesions[:] = [f"{count} {lesion}" if count > 1 else lesion for lesion, count in first_lesion_counts.items()]
    
    second_comp_lesions = [l.type for l in lesion_extraction_for_multiple_components if l.component_index == 1]
    second_lesion_counts = Counter(second_comp_lesions)
    second_comp_lesions[:] = [f"{count} {lesion}" if count > 1 else lesion for lesion, count in second_lesion_counts.items()]
    
    lesion_orphans = [f"{l.organ} {l.type}" for l in lesion_extraction_for_multiple_components if l.component_index is None]
    
    assert len(queries) == 5
    assert f"Na przekrojach {components[0].name} obecne {first_comp_lesions[0]}" == queries[2].text
    assert f"Na przekrojach {components[1].name} obecne {second_comp_lesions[0]}, {second_comp_lesions[1]}" == queries[3].text
    assert f"Na przekrojach w obrębie {lesion_orphans[0]}, ponadto w obrębie {lesion_orphans[1]}" == queries[4].text
    
def test_query_building_lesion_without_comp_index_and_organ_fields_not_in_contextual_query(component_extraction_multiple, fluid_extraction):
    lesion_extraction = [create_lesion('polip')]
    queries = build_queries(component_extraction_multiple, lesion_extraction, fluid_extraction)
    
    assert len(queries) == 2
from typing import Literal

import pytest

from app_stt.pipeline.stages.ner.entities import Lesion, Component, FluidSample, LesionExtraction, ComponentExtraction, FluidSampleExtraction
from ..qdrant.queries import detect_specimen_type, build_queries, SpecimenType


def create_component(name: str, count: int | None = None) -> Component:
    return Component(name=name, count=count)

def create_lesion(type: Literal["guz", "torbiel", "polip", "ognisko", "zmiana"]) -> Lesion:
    return Lesion(type=type)

def create_fluid(source: str, material_type: str | None = None):
    return FluidSample(source=source, material_type=material_type)

@pytest.fixture
def component_extraction():
    return ComponentExtraction(components=[Component(**c) for c in [
        {
            "name": "materiał",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "unit": "cm"
        }
    ]])

@pytest.fixture
def lesion_extraction():
    return LesionExtraction(lesions=[Lesion(**l) for l in [
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
    ]])

@pytest.fixture
def lesion_extraction_multiple_lesions_for_single_component():
    """
    To test output for many lesions with the same 'component_index',
    with few additional lesions with different 'organ' fields set.
    """
    return LesionExtraction(lesions=[
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
    ])

@pytest.fixture
def lesion_extraction_for_multiple_components():
    """
    For testing output with many lesions with different 'component_index' values.
    """
    pass
 
@pytest.fixture
def fluid_extraction():
    return FluidSampleExtraction(fluid_samples=[
        {
          "source": "z torbieli",
          "material_type": "płyn",
          "volume_ml": None,
          "color": None,
          "clarity": "klarowny",
          "consistency": None,
          "fixation": None
        }
      ])

def test_specimen_type(component_extraction, lesion_extraction, fluid_extraction):
    s_type = detect_specimen_type(component_extraction, lesion_extraction, fluid_extraction)
    assert s_type in SpecimenType

def test_specimen_type_fluid_with_component():
    component = create_component(name="nerka")
    fluid = create_fluid(source="nerka")
    
    s_type = detect_specimen_type(
        ComponentExtraction(components=[component]),
        LesionExtraction(lesions=[]),
        FluidSampleExtraction(fluid_samples=[fluid]),
    )
    
    assert s_type == SpecimenType.ORGAN
    
def test_specimen_type_fluid_with_lesion():
    lesion = create_lesion('guz')
    fluid = create_fluid('guz')
    
    s_type = detect_specimen_type(
        ComponentExtraction(components=[]),
        LesionExtraction(lesions=[lesion]),
        FluidSampleExtraction(fluid_samples=[fluid]),
    )
    
    assert s_type == SpecimenType.FLUID
    
def test_specimen_type_lesion_only():
    lesion = create_lesion('ognisko')
    s_type = detect_specimen_type(
        ComponentExtraction(components=[]),
        LesionExtraction(lesions=[lesion]),
        FluidSampleExtraction(fluid_samples=[])
    )
    
    assert s_type == SpecimenType.SMALL_EXCISION
    
def test_specimen_type_all():
    component = create_component("nerka")
    lesion = create_lesion('torbiel')
    fluid = create_fluid('torbiel', 'płyn')
    
    s_type = detect_specimen_type(ComponentExtraction(components=[component]),
                                  LesionExtraction(lesions=[lesion]),
                                  FluidSampleExtraction(fluid_samples=[fluid]))
    assert s_type == SpecimenType.ORGAN
    
def test_query_building(component_extraction, lesion_extraction, fluid_extraction):
    s_type = detect_specimen_type(component_extraction, lesion_extraction, fluid_extraction)
    queries = build_queries(component_extraction, lesion_extraction, fluid_extraction, s_type)
     
    assert len(queries) > 0
    
def test_query_building_fluid_only(fluid_extraction):
    components = ComponentExtraction(components=[])
    lesions = LesionExtraction(lesions=[])
    s_type = detect_specimen_type(components,
                                  lesions,
                                  fluid_extraction)
    queries = build_queries(components, lesions, fluid_extraction, s_type)
    
    fluid_sample = fluid_extraction.fluid_samples[0]
    
    assert len(queries) == 2    
    assert queries[0].using == 'dense'
    assert fluid_sample.source in queries[0].text
    assert fluid_sample.material_type in queries[0].text
    assert queries[1].using == 'sparse'
    assert fluid_sample.source in queries[1].text
    assert fluid_sample.material_type in queries[1].text
    
def test_query_building_all(component_extraction, lesion_extraction, fluid_extraction):
    s_type = detect_specimen_type(component_extraction, lesion_extraction, fluid_extraction)
    queries = build_queries(component_extraction, lesion_extraction, fluid_extraction, s_type)
    
    dense_parts = []
    sparse_parts = []
    dense_parts.append(component_extraction.components[0].name)
    sparse_parts.append(component_extraction.components[0].name)
    
    dense_parts.append('płyn pochodzenia ' + fluid_extraction.fluid_samples[0].source)
    sparse_parts.append('płyn ' + fluid_extraction.fluid_samples[0].source)
    
    dense_parts.append(fluid_extraction.fluid_samples[0].material_type)
    sparse_parts.append(fluid_extraction.fluid_samples[0].material_type)
    
    dense_parts.append(f'2 {lesion_extraction.lesions[0].type}')
    sparse_parts.append(lesion_extraction.lesions[0].type)
    
    assert len(queries) == 3
    assert queries[0].using == 'dense'
    assert queries[1].using == 'sparse'
    assert queries[2].using == 'dense'
        
    assert dense_parts == queries[0].text.split(', ')
    assert ' '.join(sparse_parts) == queries[1].text
    assert f"Na przekrojach {sparse_parts[0]} obecne 2 {sparse_parts[-1]}" == queries[2].text
    
def test_query_building_multiple_lession(component_extraction, lesion_extraction_multiple_lesions_for_single_component):
    s_type = detect_specimen_type(component_extraction, lesion_extraction_multiple_lesions_for_single_component, FluidSampleExtraction(fluid_samples=[]))
    queries = build_queries(component_extraction, lesion_extraction_multiple_lesions_for_single_component, FluidSampleExtraction(fluid_samples=[]), s_type)
    
    lesions = lesion_extraction_multiple_lesions_for_single_component.lesions
    
    assert len(queries) == 4
    assert (f"Na przekrojach {component_extraction.components[0].name} obecne 2 {lesions[0].type},"
    f" {lesions[2].type}, {lesions[3].type}") == queries[2].text
    assert (f"Na przekrojach w obrębie {lesions[4].organ} {lesions[4].type}"
    f", ponadto w obrębie {lesions[5].organ} {lesions[5].type}") == queries[3].text
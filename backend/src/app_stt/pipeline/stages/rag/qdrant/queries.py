from enum import Enum
from typing import List, Any, Generator, Literal
from abc import ABC, abstractmethod
from collections import defaultdict

from pydantic import BaseModel, Field

from app_stt.pipeline.stages.ner.entities import Component, ComponentExtraction, Lesion, LesionExtraction, FluidSample, FluidSampleExtraction

class ComponentWithLesion(BaseModel):
  component: Component
  lesions: List[Lesion]

class SpecimenType(Enum):
  FLUID = "fluid"
  SMALL_EXCISION = "excision"
  ORGAN = "organ_only"

class SearchQuery(BaseModel):
  text: str
  weight: float = 1.0
  using: Literal["dense", "sparse", "both"] = "both"

def detect_specimen_type(
    components: ComponentExtraction,
    lesions:    LesionExtraction,
    fluids:     FluidSampleExtraction,
) -> SpecimenType:
    components = components.components
    lesions = lesions.lesions
    has_lesion = bool(lesions)

    if not components:
      if fluids.fluid_samples:
        return SpecimenType.FLUID
      if has_lesion:
        return SpecimenType.SMALL_EXCISION

    return SpecimenType.ORGAN

def _describe_lesion_structure(l: Lesion) -> str | None:
    ltype = l.type or "zmiana"
    return ltype

def _describe_all_lesions(lesions: List[Lesion]) -> tuple[str | None, str | None]:
  used_lesion = {}
  dense_parts = []
  sparse_parts = []

  for l in lesions:
    desc = _describe_lesion_structure(l)
    if desc:
      if desc not in used_lesion.keys():
        used_lesion[desc] = 1
      else:
        used_lesion[desc] += 1

  for l, count in used_lesion.items():
    if count > 1:
      dense_parts.append(f"{count} {l}")
    else:
      dense_parts.append(l)
    sparse_parts.append(l)

  return dense_parts, sparse_parts

def _describe_component_structure(c: Component) -> str | None:
  dense_desc = f"{c.count} {c.name}" if c.count and c.count > 1 else c.name or None
  sparse_desc = c.name.lower() if c.name else None
  
  return dense_desc, sparse_desc

def _describe_fluid_structure(fs: FluidSample) -> str | None:
    dense_part = None
    sparse_part = None
    if fs.source:
      dense_part = f"płyn pochodzenia {fs.source.lower()}"
      sparse_part = f"płyn {fs.source.lower()}"
      
      if fs.material_type:
        dense_part += f", {fs.material_type.lower()}"
        sparse_part += f" {fs.material_type}"       
 
    return dense_part, sparse_part

def _get_organ_context(components: List[Component], lesions: List[Lesion]) -> Generator[Any, Any, ComponentWithLesion]:
  lesions_by_component = defaultdict(list)
  for l in lesions:
    if l.component_index is not None:
      lesions_by_component[l.component_index].append(l)

  for i, c in enumerate(components):
    c_lesions = lesions_by_component.get(i, [])
    if c_lesions:
      yield ComponentWithLesion(component = c, lesions = c_lesions)

def _get_query_from_organ_context(cl: ComponentWithLesion) -> List[SearchQuery]:
    queries = []
    c_desc = cl.component.name if cl.component.name else None

    dense_l_descs, _ = _describe_all_lesions(cl.lesions)
    if c_desc and dense_l_descs:
        queries.append(SearchQuery(
            text=f"Na przekrojach {c_desc} obecne {', '.join(dense_l_descs)}", 
            weight=1.3, 
            using="dense"
        ))
    return queries

class BaseQueryBuilder(ABC):
    def __init__(self, components: ComponentExtraction, lesions: LesionExtraction, fluids: FluidSampleExtraction, specimen_type: SpecimenType):
        self.components = components
        self.lesions = lesions
        self.fluids = fluids
        self.specimen_type = specimen_type
        
    @abstractmethod
    def build(self) -> List[SearchQuery]:
        pass

class FluidQueryBuilder(BaseQueryBuilder):
    def build(self) -> List[SearchQuery]:
        queries = []
        dense_parts = []
        sparse_parts = []

        for fs in self.fluids.fluid_samples:
          dense_desc, sparse_desc = _describe_fluid_structure(fs)
          if dense_desc:
            dense_parts.append(dense_desc)
          if sparse_desc:
            sparse_parts.append(sparse_desc)

        if dense_parts:
          queries.append(SearchQuery(text=", ".join(dense_parts), weight=1.0, using="dense"))
        if sparse_parts:
          queries.append(SearchQuery(text=" ".join(sparse_parts), weight=1.0, using="sparse"))

        return queries
    
class SmallExcisionQueryBuilder(BaseQueryBuilder):
    def build(self) -> List[SearchQuery]:
        queries = []
            
        dense_lesion_parts, sparse_lesion_parts = _describe_all_lesions(self.lesions.lesions)

        if dense_lesion_parts:
          queries.append(SearchQuery(text=", ".join(dense_lesion_parts), weight=1.0, using="dense"))
        if sparse_lesion_parts:
          queries.append(SearchQuery(text=" ".join(sparse_lesion_parts), weight=1.0, using="sparse"))  

        return queries

class OrganQueryBuilder(BaseQueryBuilder):
    def build(self) -> List[SearchQuery]:
        queries = []
        components = self.components.components
        lesions = self.lesions.lesions
        fluids = self.fluids.fluid_samples
        
        dense_struct_parts = []
        sparse_struct_parts = []

        for c in components:
          dense_desc, sparse_desc = _describe_component_structure(c)
          if dense_desc:
            dense_struct_parts.append(dense_desc)
          if sparse_desc:
            sparse_struct_parts.append(sparse_desc)
            
        for f in fluids:
          dense_desc, sparse_desc = _describe_fluid_structure(f)
          if dense_desc:
            dense_struct_parts.append(dense_desc)
          if sparse_desc:
            sparse_struct_parts.append(sparse_desc)

        lesion_dense_desc, lesion_sparse_desc = _describe_all_lesions(lesions)
        if lesion_dense_desc:
          dense_struct_parts.extend(lesion_dense_desc)
        if lesion_sparse_desc:
          sparse_struct_parts.extend(lesion_sparse_desc)

        if dense_struct_parts:
          queries.append(SearchQuery(
              text=', '.join(dense_struct_parts),
              weight=1.5,
              using="dense"
          ))

        if sparse_struct_parts:
          queries.append(SearchQuery(
            text=' '.join(sparse_struct_parts),
            weight=1.5,
            using="sparse"
          ))

        if lesions and components:
          lesion_descs = []
          assigned = set()
          for cl in _get_organ_context(components, lesions):
            queries.extend(_get_query_from_organ_context(cl))
            assigned.update(id(l) for l in cl.lesions)

          lesion_orphans = [l for l in lesions if id(l) not in assigned]
          
          for l in lesion_orphans:
            organ_ctx = l.organ or ""
            lesion_desc = _describe_lesion_structure(l)
            if lesion_desc and organ_ctx:
                ctx = f"w obrębie {organ_ctx} "
                lesion_descs.append(f"{ctx}{lesion_desc}")
          if lesion_descs:
              q_b = "Na przekrojach " + ", ponadto ".join(lesion_descs)
              queries.append(SearchQuery(
                  text=q_b,
                  weight=1.0,
                  using="dense"
              ))

        return queries

def build_queries(
    components: ComponentExtraction,
    lesions: LesionExtraction,
    fluids: FluidSampleExtraction,
    specimen_type: SpecimenType,
) -> list[SearchQuery]: 
    builder = OrganQueryBuilder(components, lesions, fluids, specimen_type)
    return builder.build()
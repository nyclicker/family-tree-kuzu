from pydantic import BaseModel
from typing import Optional, Literal

class PersonCreate(BaseModel):
    display_name: str
    sex: Literal["M","F","U"] = "U"
    notes: Optional[str] = None

class PersonOut(BaseModel):
    id: str
    display_name: str
    sex: str
    notes: Optional[str] = None

class RelCreate(BaseModel):
    from_person_id: str
    to_person_id: str
    type: Literal["PARENT_OF","SPOUSE_OF"]

class PersonUpdate(BaseModel):
    display_name: str
    sex: Literal["M","F","U"] = "U"
    notes: Optional[str] = None

class GraphOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]

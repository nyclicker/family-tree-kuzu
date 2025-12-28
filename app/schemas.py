from pydantic import BaseModel, field_validator
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
    type: Literal["CHILD_OF","EARLIEST_ANCESTOR"]

    @field_validator("to_person_id")
    @classmethod
    def validate_to_person_id(cls, v, info):
        # if earliest ancestor, to_person_id must be empty
        if info.data.get("type") == "EARLIEST_ANCESTOR":
            return None
        # if child_of, must provide parent id
        if not v:
            raise ValueError("to_person_id is required for CHILD_OF")
        return v

    

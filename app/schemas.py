from pydantic import BaseModel, field_validator
from typing import Optional, Literal


class TreeCreate(BaseModel):
    name: str
    description: Optional[str] = None


class TreeFilter(BaseModel):
    tree_id: Optional[int] = None
    tree_version_id: Optional[int] = None


class PersonCreate(BaseModel):
    display_name: str
    sex: Literal["M","F","U"] = "U"
    notes: Optional[str] = None
    tree_id: Optional[int] = None
    tree_version_id: Optional[int] = None

class PersonOut(BaseModel):
    id: str
    display_name: str
    sex: str
    notes: Optional[str] = None
    tree_id: Optional[int] = None
    version: int
    tree_version_id: Optional[int] = None

class RelCreate(BaseModel):
    from_person_id: str
    to_person_id: Optional[str]
    type: Literal["CHILD_OF","EARLIEST_ANCESTOR"]
    tree_id: Optional[int] = None
    tree_version_id: Optional[int] = None

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


class TreeImportRequest(BaseModel):
    name: Optional[str] = None
    source_filename: Optional[str] = None
    tree_id: Optional[int] = None


class TreeImportOut(BaseModel):
    tree_id: int
    tree_version_id: int
    version: int


class TreeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TreeListItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    active_version_id: Optional[int] = None


class TreeVersionItem(BaseModel):
    id: int
    tree_id: int
    version: int
    source_filename: Optional[str] = None
    created_at: Optional[str] = None
    active: bool


class DraftCreate(BaseModel):
    change_type: Literal["person","relationship"]
    payload: dict


class DraftOut(BaseModel):
    id: int
    tree_id: Optional[int]
    base_tree_version_id: Optional[int]
    change_type: str
    payload: dict
    created_at: Optional[str]

    

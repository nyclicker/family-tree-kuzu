from pydantic import BaseModel
from typing import Optional, Literal

# ── Person ──

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

# ── Auth ──

class RegisterRequest(BaseModel):
    email: str
    display_name: str
    password: str
    setup_token: Optional[str] = None
    invite_token: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    is_admin: bool

# ── Trees ──

class TreeCreate(BaseModel):
    name: str

class TreeOut(BaseModel):
    id: str
    name: str
    created_at: str
    role: str

class TreeRename(BaseModel):
    name: str

# ── Tree Members ──

class TreeMemberAdd(BaseModel):
    email: str
    role: Literal["editor", "viewer"] = "viewer"

class TreeMemberUpdate(BaseModel):
    role: Literal["editor", "viewer"]

class TreeGroupGrant(BaseModel):
    group_id: str
    role: Literal["editor", "viewer"] = "viewer"

class TreeGroupUpdate(BaseModel):
    role: Literal["editor", "viewer"]

# ── Groups ──

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class GroupUpdate(BaseModel):
    name: str
    description: Optional[str] = ""

class GroupOut(BaseModel):
    id: str
    name: str
    description: str
    created_by: str
    created_at: str

class GroupMemberAdd(BaseModel):
    email: str

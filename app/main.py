import re
import os
import hashlib
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse, Response, HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from .db import get_database, get_conn
from . import crud, schemas, graph, sharing, trees, groups, auth
from .importer import import_csv_text, import_db_file

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Legacy admin password (kept for backwards compatibility during transition)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_cookie_secret = os.environ.get("COOKIE_SECRET", secrets.token_hex(16))

# Ensure auth module uses the same cookie secret
auth.COOKIE_SECRET = _cookie_secret


def _make_admin_token():
    return hashlib.sha256(f"{ADMIN_PASSWORD}:{_cookie_secret}".encode()).hexdigest()


# Paths that don't require authentication
_PUBLIC_PATHS = {"/login", "/health", "/api/auth/register", "/api/auth/login", "/api/auth/logout", "/api/auth/setup-status"}
_PUBLIC_PREFIXES = ("/view/", "/auth/magic/")


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that requires session auth OR legacy admin auth."""
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Public paths
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)
        # Static assets
        if path.startswith("/web/"):
            return await call_next(request)
        if path == "/":
            return await call_next(request)
        # API datasets listing is public
        if path == "/api/datasets":
            return await call_next(request)
        # Check session cookie (new auth)
        session = request.cookies.get(auth.SESSION_COOKIE)
        user_id = auth.verify_session_token(session)
        if user_id:
            return await call_next(request)
        # Check legacy admin_token cookie
        if ADMIN_PASSWORD:
            admin_token = request.cookies.get("admin_token")
            if admin_token == _make_admin_token():
                return await call_next(request)
        # Not authenticated
        # For API calls, return 401
        if path.startswith("/api/"):
            return Response(content='{"detail":"Not authenticated"}',
                            status_code=401, media_type="application/json")
        return RedirectResponse("/login", status_code=302)


def _clean_display_names(conn, tree_id=""):
    """Post-import: strip \\n suffixes and parenthetical disambiguations from display names."""
    if tree_id:
        result = conn.execute(
            "MATCH (p:Person) WHERE p.tree_id = $tid RETURN p.id, p.display_name",
            {"tid": tree_id}
        )
    else:
        result = conn.execute("MATCH (p:Person) RETURN p.id, p.display_name")
    updates = []
    while result.has_next():
        row = result.get_next()
        pid, name = row[0], row[1]
        clean = name
        # Remove newline and everything after it
        nl = clean.find('\n')
        if nl != -1:
            clean = clean[:nl]
        # Remove trailing parenthetical e.g. " (Desta)"
        clean = re.sub(r'\s*\([^)]*\)\s*$', '', clean)
        clean = clean.strip()
        if clean and clean != name:
            updates.append((pid, clean))
    for pid, clean in updates:
        conn.execute(
            "MATCH (p:Person) WHERE p.id = $id SET p.display_name = $name",
            {"id": pid, "name": clean}
        )


class DatasetLoadRequest(BaseModel):
    files: list[str]
    combine: bool = False


def _run_migration(conn):
    """On startup, if there are existing Person nodes with no tree_id, migrate them."""
    # Check if there are un-migrated people (tree_id is empty)
    result = conn.execute(
        "MATCH (p:Person) WHERE p.tree_id = '' OR p.tree_id IS NULL RETURN count(*)"
    )
    if result.has_next():
        count = result.get_next()[0]
        if count > 0:
            # Check if a Default tree already exists
            result2 = conn.execute(
                "MATCH (t:FamilyTree) WHERE t.name = 'Default' RETURN t.id"
            )
            if result2.has_next():
                default_tid = result2.get_next()[0]
            else:
                from datetime import datetime, timezone
                import uuid
                default_tid = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "CREATE (t:FamilyTree {id: $id, name: 'Default', created_at: $ts})",
                    {"id": default_tid, "ts": now}
                )
            # Assign all un-migrated people to the default tree
            conn.execute(
                "MATCH (p:Person) WHERE p.tree_id = '' OR p.tree_id IS NULL "
                "SET p.tree_id = $tid",
                {"tid": default_tid}
            )
            # Also migrate share links
            conn.execute(
                "MATCH (s:ShareLink) WHERE s.tree_id = '' OR s.tree_id IS NULL "
                "SET s.tree_id = $tid",
                {"tid": default_tid}
            )


@asynccontextmanager
async def lifespan(app):
    db = get_database()
    import kuzu
    conn = kuzu.Connection(db)
    _run_migration(conn)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionAuthMiddleware)


# ═══════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
def register(body: schemas.RegisterRequest, conn=Depends(get_conn)):
    """Register a new user. First user requires SETUP_TOKEN; subsequent users require invite."""
    user_count = auth.count_users(conn)
    if user_count == 0:
        # First user: require setup token
        if not auth.SETUP_TOKEN:
            raise HTTPException(400, "No SETUP_TOKEN configured. Set it as an environment variable.")
        if body.setup_token != auth.SETUP_TOKEN:
            raise HTTPException(403, "Invalid setup token")
        is_admin = True
    else:
        # Subsequent users: for now, any existing user can create accounts
        # (invite system can be expanded later)
        is_admin = False

    try:
        user = auth.create_user(conn, body.email, body.display_name, body.password, is_admin)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # If first user and there's a default tree with no owner, assign ownership
    if is_admin:
        result = conn.execute("MATCH (t:FamilyTree) RETURN t.id")
        while result.has_next():
            tid = result.get_next()[0]
            owner_id = trees.get_tree_owner_id(conn, tid)
            if not owner_id:
                conn.execute(
                    "MATCH (u:User), (t:FamilyTree) WHERE u.id = $uid AND t.id = $tid "
                    "CREATE (u)-[:OWNS]->(t)",
                    {"uid": user["id"], "tid": tid}
                )

    # Auto-login: set session cookie
    response_data = {"id": user["id"], "email": user["email"],
                     "display_name": user["display_name"], "is_admin": user["is_admin"]}
    from fastapi.responses import JSONResponse
    response = JSONResponse(response_data)
    token = auth.create_session_token(user["id"])
    response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/api/auth/login")
def login(body: schemas.LoginRequest, conn=Depends(get_conn)):
    """Login with email + password."""
    user = auth.authenticate_user(conn, body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    from fastapi.responses import JSONResponse
    response = JSONResponse({
        "id": user["id"], "email": user["email"],
        "display_name": user["display_name"], "is_admin": user["is_admin"]
    })
    token = auth.create_session_token(user["id"])
    response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/api/auth/logout")
def logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.SESSION_COOKIE)
    response.delete_cookie("admin_token")
    return response


@app.get("/auth/magic/{token}")
def magic_login(token: str, conn=Depends(get_conn)):
    """Login via magic link. Sets session cookie and redirects to /."""
    user = auth.get_user_by_magic_token(conn, token)
    if not user:
        raise HTTPException(404, "Invalid or expired magic link")
    response = RedirectResponse("/", status_code=302)
    session_token = auth.create_session_token(user["id"])
    response.set_cookie(auth.SESSION_COOKIE, session_token, httponly=True, samesite="lax")
    return response


@app.get("/api/auth/me")
def me(user=Depends(auth.get_current_user)):
    return user


# ═══════════════════════════════════════════════════════════════
# TREE MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/trees")
def list_trees(user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    return trees.list_user_trees(conn, user["id"])


@app.post("/api/trees")
def create_tree(body: schemas.TreeCreate, user=Depends(auth.get_current_user),
                conn=Depends(get_conn)):
    return trees.create_tree(conn, body.name, user["id"])


@app.put("/api/trees/{tree_id}")
def rename_tree(tree_id: str, body: schemas.TreeRename,
                user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.rename_tree(conn, tree_id, body.name)
    return {"ok": True}


@app.delete("/api/trees/{tree_id}")
def delete_tree(tree_id: str, user=Depends(auth.get_current_user),
                conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.delete_tree(conn, tree_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# TREE SHARING ENDPOINTS (owner only)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/trees/{tree_id}/members")
def list_members(tree_id: str, user=Depends(auth.get_current_user),
                 conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    return trees.list_tree_members(conn, tree_id)


@app.post("/api/trees/{tree_id}/members")
def add_member(tree_id: str, body: schemas.TreeMemberAdd, request: Request,
               user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    target_user = auth.get_user_by_email(conn, body.email)
    if not target_user:
        # Auto-create invited user (no password)
        display_name = body.email.split("@")[0]
        target_user = auth.create_user_invited(conn, body.email, display_name)
    # Can't add owner to their own tree as a member
    owner_id = trees.get_tree_owner_id(conn, tree_id)
    if target_user["id"] == owner_id:
        raise HTTPException(400, "Cannot add the owner as a member")
    trees.grant_user_access(conn, tree_id, target_user["id"], body.role)
    # Generate magic link for the member
    token = auth.ensure_magic_token(conn, target_user["id"])
    base_url = str(request.base_url).rstrip("/")
    magic_link = f"{base_url}/auth/magic/{token}"
    return {"ok": True, "user_id": target_user["id"], "magic_link": magic_link}


@app.put("/api/trees/{tree_id}/members/{uid}")
def update_member(tree_id: str, uid: str, body: schemas.TreeMemberUpdate,
                  user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.update_user_access(conn, tree_id, uid, body.role)
    return {"ok": True}


@app.delete("/api/trees/{tree_id}/members/{uid}")
def remove_member(tree_id: str, uid: str, user=Depends(auth.get_current_user),
                  conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.revoke_user_access(conn, tree_id, uid)
    return {"ok": True}


@app.get("/api/trees/{tree_id}/members/{uid}/magic-link")
def get_member_magic_link(tree_id: str, uid: str, request: Request,
                          user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    """Owner-only: get (or generate) the magic login link for a member."""
    trees.require_role(conn, user["id"], tree_id, "owner")
    token = auth.ensure_magic_token(conn, uid)
    base_url = str(request.base_url).rstrip("/")
    return {"magic_link": f"{base_url}/auth/magic/{token}"}


@app.post("/api/trees/{tree_id}/groups")
def grant_group(tree_id: str, body: schemas.TreeGroupGrant,
                user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    group = groups.get_group(conn, body.group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    trees.grant_group_access(conn, tree_id, body.group_id, body.role)
    return {"ok": True}


@app.put("/api/trees/{tree_id}/groups/{gid}")
def update_group_access(tree_id: str, gid: str, body: schemas.TreeGroupUpdate,
                        user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.update_group_access(conn, tree_id, gid, body.role)
    return {"ok": True}


@app.delete("/api/trees/{tree_id}/groups/{gid}")
def revoke_group(tree_id: str, gid: str, user=Depends(auth.get_current_user),
                 conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    trees.revoke_group_access(conn, tree_id, gid)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════
# GROUP MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/groups")
def list_groups_endpoint(user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    if user["is_admin"]:
        return groups.list_all_groups(conn)
    return groups.list_user_groups(conn, user["id"])


@app.post("/api/groups")
def create_group(body: schemas.GroupCreate, user=Depends(auth.get_current_user),
                 conn=Depends(get_conn)):
    return groups.create_group(conn, body.name, body.description or "", user["id"])


@app.put("/api/groups/{group_id}")
def update_group(group_id: str, body: schemas.GroupUpdate,
                 user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized to manage this group")
    groups.update_group(conn, group_id, body.name, body.description or "")
    return {"ok": True}


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str, user=Depends(auth.get_current_user),
                 conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized to manage this group")
    groups.delete_group(conn, group_id)
    return {"ok": True}


@app.get("/api/groups/{group_id}/members")
def list_group_members(group_id: str, user=Depends(auth.get_current_user),
                       conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized")
    return groups.list_members(conn, group_id)


@app.post("/api/groups/{group_id}/members")
def add_group_member(group_id: str, body: schemas.GroupMemberAdd,
                     user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized")
    target = auth.get_user_by_email(conn, body.email)
    if not target:
        raise HTTPException(404, f"No user found with email {body.email}")
    groups.add_member(conn, group_id, target["id"])
    return {"ok": True, "user_id": target["id"]}


@app.delete("/api/groups/{group_id}/members/{uid}")
def remove_group_member(group_id: str, uid: str,
                        user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized")
    groups.remove_member(conn, group_id, uid)
    return {"ok": True}


@app.get("/api/groups/{group_id}/trees")
def list_group_trees(group_id: str, user=Depends(auth.get_current_user),
                     conn=Depends(get_conn)):
    if not groups.can_manage_group(conn, group_id, user["id"], user["is_admin"]):
        raise HTTPException(403, "Not authorized")
    return groups.list_group_trees(conn, group_id)


# ═══════════════════════════════════════════════════════════════
# TREE-SCOPED DATA ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/trees/{tree_id}/people", response_model=list[schemas.PersonOut])
def tree_people(tree_id: str, user=Depends(auth.get_current_user),
                conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    return crud.list_people(conn, tree_id=tree_id)


@app.post("/api/trees/{tree_id}/people", response_model=schemas.PersonOut)
def tree_add_person(tree_id: str, body: schemas.PersonCreate,
                    user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    return crud.create_person(conn, body.display_name, body.sex, body.notes, tree_id=tree_id,
                              birth_date=body.birth_date, death_date=body.death_date,
                              is_deceased=body.is_deceased)


@app.put("/api/trees/{tree_id}/people/{person_id}", response_model=schemas.PersonOut)
def tree_update_person(tree_id: str, person_id: str, body: schemas.PersonUpdate,
                       user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    p = crud.update_person(conn, person_id, body.display_name, body.sex, body.notes,
                           tree_id=tree_id, birth_date=body.birth_date,
                           death_date=body.death_date, is_deceased=body.is_deceased)
    if not p:
        raise HTTPException(404, "Person not found")
    return p


@app.delete("/api/trees/{tree_id}/people/{person_id}")
def tree_delete_person(tree_id: str, person_id: str,
                       user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    crud.delete_person(conn, person_id, tree_id=tree_id)
    return {"ok": True}


@app.get("/api/trees/{tree_id}/people/{person_id}/parents",
         response_model=list[schemas.PersonOut])
def tree_get_parents(tree_id: str, person_id: str,
                     user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    return crud.get_parents(conn, person_id)


class SetParentRequest(BaseModel):
    existing_person_id: str | None = None
    display_name: str | None = None
    sex: str = "U"
    notes: str | None = None


@app.post("/api/trees/{tree_id}/people/{person_id}/set-parent")
def tree_set_parent(tree_id: str, person_id: str, body: SetParentRequest,
                    user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    existing_parents = crud.get_parents(conn, person_id)
    removed = []
    for parent in existing_parents:
        crud.delete_parent_relationship(conn, parent["id"], person_id)
        removed.append(parent["display_name"])

    if body.existing_person_id:
        parent_person = crud.get_person(conn, body.existing_person_id, tree_id=tree_id)
        if not parent_person:
            raise HTTPException(404, "Selected parent person not found")
        if body.existing_person_id == person_id:
            raise HTTPException(400, "A person cannot be their own parent")
    elif body.display_name:
        parent_person = crud.create_person(conn, body.display_name, body.sex, body.notes,
                                           tree_id=tree_id)
    else:
        raise HTTPException(400, "Provide existing_person_id or display_name")

    crud.create_relationship(conn, parent_person["id"], person_id, "PARENT_OF")
    return {"parent": parent_person, "removed_parents": removed}


@app.get("/api/trees/{tree_id}/people/{person_id}/relationship-counts")
def tree_relationship_counts(tree_id: str, person_id: str,
                             user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    return {
        "parents": crud.count_parents(conn, person_id),
        "spouses": crud.count_spouses(conn, person_id),
    }


# ── Comment endpoints ──

@app.get("/api/trees/{tree_id}/people/{person_id}/comments",
         response_model=list[schemas.CommentOut])
def tree_list_comments(tree_id: str, person_id: str,
                       user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    return crud.list_comments(conn, person_id, tree_id)


@app.post("/api/trees/{tree_id}/people/{person_id}/comments",
          response_model=schemas.CommentOut)
def tree_add_comment(tree_id: str, person_id: str, body: schemas.CommentCreate,
                     user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    person = crud.get_person(conn, person_id, tree_id)
    if not person:
        raise HTTPException(404, "Person not found")
    return crud.create_comment(conn, person_id, tree_id,
                               user["id"], user["display_name"], body.content)


@app.delete("/api/trees/{tree_id}/people/{person_id}/comments/{comment_id}")
def tree_delete_comment(tree_id: str, person_id: str, comment_id: str,
                        user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    comment = crud.get_comment(conn, comment_id)
    if not comment:
        raise HTTPException(404, "Comment not found")
    if comment["author_id"] != user["id"]:
        raise HTTPException(403, "You can only delete your own comments")
    crud.delete_comment(conn, comment_id)
    return {"ok": True}


@app.post("/api/trees/{tree_id}/relationships")
def tree_add_rel(tree_id: str, body: schemas.RelCreate,
                 user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    if body.type == "PARENT_OF":
        child_parents = crud.count_parents(conn, body.to_person_id)
        if child_parents >= 1:
            raise HTTPException(400, "This person already has a parent. Use 'Replace Parent' to change it.")
    if body.type == "SPOUSE_OF":
        from_spouses = crud.count_spouses(conn, body.from_person_id)
        to_spouses = crud.count_spouses(conn, body.to_person_id)
        if from_spouses >= 1:
            raise HTTPException(400, "This person already has a spouse.")
        if to_spouses >= 1:
            raise HTTPException(400, "The other person already has a spouse.")
    result = crud.create_relationship(conn, body.from_person_id, body.to_person_id, body.type)
    if body.type == "SPOUSE_OF":
        merged = crud.merge_spouse_children(conn, body.from_person_id, body.to_person_id)
        if merged:
            result["merged_children"] = merged
    return result


@app.delete("/api/trees/{tree_id}/relationships/{rel_id}")
def tree_delete_rel(tree_id: str, rel_id: str,
                    user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    crud.delete_relationship(conn, rel_id)
    return {"ok": True}


@app.get("/api/trees/{tree_id}/graph", response_model=schemas.GraphOut)
def tree_graph(tree_id: str, user=Depends(auth.get_current_user),
               conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    return graph.build_graph(conn, tree_id=tree_id)


@app.post("/api/trees/{tree_id}/import/dataset")
def tree_import_dataset(tree_id: str, body: DatasetLoadRequest,
                        user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    if not DATA_DIR.exists():
        return {"error": "No data directory"}

    all_people = 0
    all_rels = 0
    all_fixes = []
    all_errors = []
    dataset_names = []

    for i, filename in enumerate(body.files):
        filepath = DATA_DIR / filename
        if not filepath.exists():
            all_errors.append({"line": 0, "type": "file_not_found",
                               "message": f"File not found: {filename}"})
            continue
        clear = (i == 0 and not body.combine)
        result = import_csv_text(
            conn, filepath.read_text(encoding="utf-8"),
            dataset=filepath.stem, clear_first=clear, tree_id=tree_id
        )
        all_people = result["people"]
        all_rels += result["relationships"]
        all_fixes.extend(result["auto_fixes"])
        all_errors.extend(result["errors"])
        dataset_names.append(filepath.stem)

    _clean_display_names(conn, tree_id=tree_id)
    all_people = len(crud.list_people(conn, tree_id=tree_id))

    name = ", ".join(dataset_names) if len(dataset_names) > 1 else (dataset_names[0] if dataset_names else "")
    return {
        "people": all_people, "relationships": all_rels,
        "auto_fixes": all_fixes, "errors": all_errors,
        "dataset_name": name,
    }


@app.post("/api/trees/{tree_id}/import/upload")
async def tree_import_upload(tree_id: str, file: UploadFile = File(...),
                             user=Depends(auth.get_current_user),
                             conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "editor")
    contents = await file.read()
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext == ".db":
        result = import_db_file(conn, contents, tree_id=tree_id)
    elif ext in (".csv", ".txt", ""):
        text = contents.decode("utf-8", errors="replace")
        result = import_csv_text(conn, text, tree_id=tree_id)
    else:
        return {"error": f"Unsupported file type: {ext}. Use .csv, .txt, or .db"}
    _clean_display_names(conn, tree_id=tree_id)
    result["people"] = len(crud.list_people(conn, tree_id=tree_id))
    result["dataset_name"] = Path(name).stem
    return result


@app.post("/api/trees/{tree_id}/clear")
def tree_clear_data(tree_id: str, user=Depends(auth.get_current_user),
                    conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    crud.clear_all(conn, tree_id=tree_id)
    return {"ok": True}


@app.get("/api/trees/{tree_id}/export/csv")
def tree_export_csv(tree_id: str, user=Depends(auth.get_current_user),
                    conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "viewer")
    import csv as csv_mod, io as io_mod

    people_list = crud.list_people(conn, tree_id=tree_id)
    id_to_person = {p["id"]: p for p in people_list}

    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF"]:
        result = conn.execute(
            f"MATCH (a:Person)-[r:{rel_type}]->(b:Person) RETURN a.id, b.id"
        )
        while result.has_next():
            row = result.get_next()
            # Only include edges between people in this tree
            if row[0] in id_to_person and row[1] in id_to_person:
                edges.append({"from_id": row[0], "to_id": row[1], "type": rel_type})

    children_ids = {e["to_id"] for e in edges if e["type"] == "PARENT_OF"}
    buf = io_mod.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(["Person 1", "Relation", "Person 2", "Gender", "Details"])

    for p in people_list:
        if p["id"] not in children_ids:
            dn = p["display_name"].replace("\n", "\\n")
            writer.writerow([dn, "Earliest Ancestor", "", p["sex"], p["notes"] or ""])

    for e in edges:
        p1 = id_to_person.get(e["from_id"])
        p2 = id_to_person.get(e["to_id"])
        if not p1 or not p2:
            continue
        dn1 = p1["display_name"].replace("\n", "\\n")
        dn2 = p2["display_name"].replace("\n", "\\n")
        if e["type"] == "PARENT_OF":
            writer.writerow([dn2, "Child", dn1, p2["sex"], p2["notes"] or ""])
        elif e["type"] == "SPOUSE_OF":
            writer.writerow([dn1, "Spouse", dn2, "", ""])

    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=family_tree.csv"}
    )


# ── Tree-scoped sharing endpoints ──

class ShareCreateRequest(BaseModel):
    dataset: str = ""


class ViewerAddRequest(BaseModel):
    email: str
    name: str = ""


@app.post("/api/trees/{tree_id}/shares")
def tree_create_share(tree_id: str, body: ShareCreateRequest,
                      user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    tree = trees.get_tree(conn, tree_id)
    dataset = body.dataset or (tree["name"] if tree else "")
    link = sharing.create_share_link(conn, dataset, tree_id=tree_id)
    return link


@app.get("/api/trees/{tree_id}/shares")
def tree_list_shares(tree_id: str, user=Depends(auth.get_current_user),
                     conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    links = sharing.list_share_links(conn, tree_id=tree_id)
    for link in links:
        link["viewers"] = sharing.list_viewers(conn, link["token"])
    return links


@app.delete("/api/trees/{tree_id}/shares/{token}")
def tree_delete_share(tree_id: str, token: str,
                      user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    sharing.delete_share_link(conn, token)
    return {"ok": True}


@app.post("/api/trees/{tree_id}/shares/{token}/viewers")
def tree_add_share_viewer(tree_id: str, token: str, body: ViewerAddRequest,
                          user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    return sharing.add_viewer(conn, token, body.email, body.name)


@app.delete("/api/trees/{tree_id}/shares/{token}/viewers/{viewer_id}")
def tree_remove_share_viewer(tree_id: str, token: str, viewer_id: str,
                             user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    sharing.remove_viewer(conn, token, viewer_id)
    return {"ok": True}


@app.get("/api/trees/{tree_id}/shares/{token}/viewers")
def tree_get_share_viewers(tree_id: str, token: str,
                           user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    return sharing.list_viewers(conn, token)


@app.get("/api/trees/{tree_id}/shares/{token}/access-log")
def tree_get_access_log(tree_id: str, token: str,
                        user=Depends(auth.get_current_user), conn=Depends(get_conn)):
    trees.require_role(conn, user["id"], tree_id, "owner")
    return sharing.get_access_log(conn, token)


# ═══════════════════════════════════════════════════════════════
# LEGACY UNSCOPED ENDPOINTS (for backward compatibility)
# ═══════════════════════════════════════════════════════════════

@app.get("/people", response_model=list[schemas.PersonOut])
def people(conn=Depends(get_conn)):
    return crud.list_people(conn)


@app.post("/people", response_model=schemas.PersonOut)
def add_person(body: schemas.PersonCreate, conn=Depends(get_conn)):
    return crud.create_person(conn, body.display_name, body.sex, body.notes)


@app.post("/relationships")
def add_rel(body: schemas.RelCreate, conn=Depends(get_conn)):
    if body.type == "PARENT_OF":
        child_parents = crud.count_parents(conn, body.to_person_id)
        if child_parents >= 1:
            raise HTTPException(400, "This person already has a parent. Use 'Replace Parent' to change it.")
    if body.type == "SPOUSE_OF":
        from_spouses = crud.count_spouses(conn, body.from_person_id)
        to_spouses = crud.count_spouses(conn, body.to_person_id)
        if from_spouses >= 1:
            raise HTTPException(400, "This person already has a spouse.")
        if to_spouses >= 1:
            raise HTTPException(400, "The other person already has a spouse.")
    result = crud.create_relationship(conn, body.from_person_id, body.to_person_id, body.type)
    if body.type == "SPOUSE_OF":
        merged = crud.merge_spouse_children(conn, body.from_person_id, body.to_person_id)
        if merged:
            result["merged_children"] = merged
    return result


@app.put("/people/{person_id}", response_model=schemas.PersonOut)
def update_person(person_id: str, body: schemas.PersonUpdate, conn=Depends(get_conn)):
    p = crud.update_person(conn, person_id, body.display_name, body.sex, body.notes)
    if not p:
        raise HTTPException(404, "Person not found")
    return p


@app.delete("/people/{person_id}")
def delete_person(person_id: str, conn=Depends(get_conn)):
    crud.delete_person(conn, person_id)
    return {"ok": True}


@app.delete("/relationships/{rel_id}")
def delete_rel(rel_id: str, conn=Depends(get_conn)):
    crud.delete_relationship(conn, rel_id)
    return {"ok": True}


@app.get("/people/{person_id}/parents", response_model=list[schemas.PersonOut])
def get_parents(person_id: str, conn=Depends(get_conn)):
    return crud.get_parents(conn, person_id)


@app.post("/people/{person_id}/set-parent")
def set_parent(person_id: str, body: SetParentRequest, conn=Depends(get_conn)):
    existing_parents = crud.get_parents(conn, person_id)
    removed = []
    for parent in existing_parents:
        crud.delete_parent_relationship(conn, parent["id"], person_id)
        removed.append(parent["display_name"])
    if body.existing_person_id:
        parent_person = crud.get_person(conn, body.existing_person_id)
        if not parent_person:
            raise HTTPException(404, "Selected parent person not found")
        if body.existing_person_id == person_id:
            raise HTTPException(400, "A person cannot be their own parent")
    elif body.display_name:
        parent_person = crud.create_person(conn, body.display_name, body.sex, body.notes)
    else:
        raise HTTPException(400, "Provide existing_person_id or display_name")
    crud.create_relationship(conn, parent_person["id"], person_id, "PARENT_OF")
    return {"parent": parent_person, "removed_parents": removed}


@app.get("/people/{person_id}/relationship-counts")
def relationship_counts(person_id: str, conn=Depends(get_conn)):
    return {
        "parents": crud.count_parents(conn, person_id),
        "spouses": crud.count_spouses(conn, person_id),
    }


@app.get("/graph", response_model=schemas.GraphOut)
def get_graph(conn=Depends(get_conn)):
    return graph.build_graph(conn)


# Legacy sharing endpoints
@app.post("/api/shares")
def create_share(body: ShareCreateRequest, conn=Depends(get_conn)):
    link = sharing.create_share_link(conn, body.dataset)
    return link


@app.get("/api/shares")
def list_shares(conn=Depends(get_conn)):
    links = sharing.list_share_links(conn)
    for link in links:
        link["viewers"] = sharing.list_viewers(conn, link["token"])
    return links


@app.delete("/api/shares/{token}")
def delete_share(token: str, conn=Depends(get_conn)):
    sharing.delete_share_link(conn, token)
    return {"ok": True}


@app.post("/api/shares/{token}/viewers")
def add_share_viewer(token: str, body: ViewerAddRequest, conn=Depends(get_conn)):
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    return sharing.add_viewer(conn, token, body.email, body.name)


@app.delete("/api/shares/{token}/viewers/{viewer_id}")
def remove_share_viewer(token: str, viewer_id: str, conn=Depends(get_conn)):
    sharing.remove_viewer(conn, token, viewer_id)
    return {"ok": True}


@app.get("/api/shares/{token}/viewers")
def get_share_viewers(token: str, conn=Depends(get_conn)):
    return sharing.list_viewers(conn, token)


@app.get("/api/shares/{token}/access-log")
def get_share_access_log(token: str, conn=Depends(get_conn)):
    return sharing.get_access_log(conn, token)


# Legacy data endpoints
@app.post("/api/import/dataset")
def import_dataset(body: DatasetLoadRequest, conn=Depends(get_conn)):
    if not DATA_DIR.exists():
        return {"error": "No data directory"}
    all_people = 0
    all_rels = 0
    all_fixes = []
    all_errors = []
    dataset_names = []
    for i, filename in enumerate(body.files):
        filepath = DATA_DIR / filename
        if not filepath.exists():
            all_errors.append({"line": 0, "type": "file_not_found",
                               "message": f"File not found: {filename}"})
            continue
        clear = (i == 0 and not body.combine)
        result = import_csv_text(conn, filepath.read_text(encoding="utf-8"),
                                 dataset=filepath.stem, clear_first=clear)
        all_people = result["people"]
        all_rels += result["relationships"]
        all_fixes.extend(result["auto_fixes"])
        all_errors.extend(result["errors"])
        dataset_names.append(filepath.stem)
    _clean_display_names(conn)
    all_people = len(crud.list_people(conn))
    name = ", ".join(dataset_names) if len(dataset_names) > 1 else (dataset_names[0] if dataset_names else "")
    return {"people": all_people, "relationships": all_rels,
            "auto_fixes": all_fixes, "errors": all_errors, "dataset_name": name}


@app.post("/api/clear")
def clear_data(conn=Depends(get_conn)):
    crud.clear_all(conn)
    return {"ok": True}


@app.post("/api/import/upload")
async def import_upload(file: UploadFile = File(...), conn=Depends(get_conn)):
    contents = await file.read()
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext == ".db":
        result = import_db_file(conn, contents)
    elif ext in (".csv", ".txt", ""):
        text = contents.decode("utf-8", errors="replace")
        result = import_csv_text(conn, text)
    else:
        return {"error": f"Unsupported file type: {ext}. Use .csv, .txt, or .db"}
    _clean_display_names(conn)
    result["people"] = len(crud.list_people(conn))
    result["dataset_name"] = Path(name).stem
    return result


@app.get("/api/export/csv")
def export_csv(conn=Depends(get_conn)):
    import csv as csv_mod, io as io_mod
    people_list = crud.list_people(conn)
    id_to_person = {p["id"]: p for p in people_list}
    edges = []
    for rel_type in ["PARENT_OF", "SPOUSE_OF"]:
        result = conn.execute(f"MATCH (a:Person)-[r:{rel_type}]->(b:Person) RETURN a.id, b.id")
        while result.has_next():
            row = result.get_next()
            edges.append({"from_id": row[0], "to_id": row[1], "type": rel_type})
    children_ids = {e["to_id"] for e in edges if e["type"] == "PARENT_OF"}
    buf = io_mod.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(["Person 1", "Relation", "Person 2", "Gender", "Details"])
    for p in people_list:
        if p["id"] not in children_ids:
            dn = p["display_name"].replace("\n", "\\n")
            writer.writerow([dn, "Earliest Ancestor", "", p["sex"], p["notes"] or ""])
    for e in edges:
        p1 = id_to_person.get(e["from_id"])
        p2 = id_to_person.get(e["to_id"])
        if not p1 or not p2:
            continue
        dn1 = p1["display_name"].replace("\n", "\\n")
        dn2 = p2["display_name"].replace("\n", "\\n")
        if e["type"] == "PARENT_OF":
            writer.writerow([dn2, "Child", dn1, p2["sex"], p2["notes"] or ""])
        elif e["type"] == "SPOUSE_OF":
            writer.writerow([dn1, "Spouse", dn2, "", ""])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=family_tree.csv"})


# ═══════════════════════════════════════════════════════════════
# PUBLIC / VIEWER ENDPOINTS (unchanged)
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/auth/setup-status")
def setup_status(conn=Depends(get_conn)):
    """Public endpoint: returns whether initial setup (first user) is needed."""
    return {"needs_setup": auth.count_users(conn) == 0}


@app.get("/api/datasets")
def list_datasets():
    if not DATA_DIR.exists():
        return []
    files = sorted(list(DATA_DIR.glob("*.csv")) + list(DATA_DIR.glob("*.txt")))
    return [{"name": f.stem, "filename": f.name} for f in files]


class ViewerAuthRequest(BaseModel):
    email: str


@app.post("/view/{token}/auth")
def viewer_auth(token: str, body: ViewerAuthRequest, request: Request, conn=Depends(get_conn)):
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer = sharing.check_viewer_access(conn, token, body.email)
    if not viewer:
        raise HTTPException(403, "You don't have access to this tree. Contact the owner to request access.")
    ip = request.client.host if request.client else ""
    sharing.log_access(conn, token, viewer["id"], ip)
    return {"ok": True, "viewer": viewer, "dataset": link["dataset"],
            "tree_id": link.get("tree_id", "")}


@app.get("/view/{token}/graph")
def viewer_graph(token: str, email: str, conn=Depends(get_conn)):
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer = sharing.check_viewer_access(conn, token, email)
    if not viewer:
        raise HTTPException(403, "Access denied")
    # Use tree_id if available, fall back to dataset
    if link.get("tree_id"):
        return graph.build_graph(conn, tree_id=link["tree_id"])
    return graph.build_graph(conn, dataset=link["dataset"])


@app.get("/view/{token}", response_class=HTMLResponse)
def viewer_page(token: str, conn=Depends(get_conn)):
    link = sharing.get_share_link(conn, token)
    if not link:
        raise HTTPException(404, "Share link not found")
    viewer_html = Path(__file__).resolve().parent.parent / "web" / "viewer.html"
    if not viewer_html.exists():
        raise HTTPException(500, "Viewer page not found")
    return HTMLResponse(viewer_html.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════
# UI ROUTES
# ═══════════════════════════════════════════════════════════════

_NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse("web/index.html", headers=_NO_CACHE)


@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
def ui():
    return FileResponse("web/index.html", headers=_NO_CACHE)


@app.get("/web/app.js", include_in_schema=False)
def ui_js():
    return FileResponse("web/app.js", headers=_NO_CACHE)


@app.get("/logout", include_in_schema=False)
def logout_page():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(auth.SESSION_COOKIE)
    response.delete_cookie("admin_token")
    return response

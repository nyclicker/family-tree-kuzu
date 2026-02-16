"""Tests for app/auth.py — passwords, tokens, user CRUD, magic links."""
import pytest
from app import auth


# ── Password validation ──

class TestValidatePassword:
    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 8"):
            auth.validate_password("short")

    def test_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            auth.validate_password("a" * 73)

    def test_valid(self):
        auth.validate_password("validpass")  # no exception


# ── Password hashing ──

class TestHashAndVerify:
    def test_hash_and_verify_correct(self):
        h = auth.hash_password("mypassword")
        assert auth.verify_password("mypassword", h) is True

    def test_verify_wrong_password(self):
        h = auth.hash_password("mypassword")
        assert auth.verify_password("wrongpassword", h) is False

    def test_verify_invalid_hash(self):
        assert auth.verify_password("any", "not-a-valid-hash") is False


# ── Session tokens ──

class TestSessionTokens:
    def test_create_and_verify(self):
        token = auth.create_session_token("user-123")
        result = auth.verify_session_token(token)
        assert result == "user-123"

    def test_invalid_signature(self):
        token = auth.create_session_token("user-123")
        parts = token.split(":")
        parts[2] = "badsig"
        tampered = ":".join(parts)
        assert auth.verify_session_token(tampered) is None

    def test_tampered_payload(self):
        token = auth.create_session_token("user-123")
        parts = token.split(":")
        parts[0] = "hacker"
        tampered = ":".join(parts)
        assert auth.verify_session_token(tampered) is None

    def test_empty_token(self):
        assert auth.verify_session_token("") is None
        assert auth.verify_session_token(None) is None

    def test_malformed_token(self):
        assert auth.verify_session_token("just-one-part") is None
        assert auth.verify_session_token("two:parts") is None


# ── User CRUD ──

class TestUserCRUD:
    def test_create_user(self, conn):
        user = auth.create_user(conn, "new@example.com", "New User", "password123")
        assert user["email"] == "new@example.com"
        assert user["display_name"] == "New User"
        assert "id" in user

    def test_create_duplicate_email(self, conn):
        auth.create_user(conn, "dup@example.com", "User1", "password123")
        with pytest.raises(ValueError, match="already exists"):
            auth.create_user(conn, "dup@example.com", "User2", "password456")

    def test_create_case_insensitive_email(self, conn):
        auth.create_user(conn, "Case@Example.COM", "User", "password123")
        with pytest.raises(ValueError, match="already exists"):
            auth.create_user(conn, "case@example.com", "User2", "password456")

    def test_get_user_by_email(self, conn, user_alice):
        found = auth.get_user_by_email(conn, "alice@example.com")
        assert found is not None
        assert found["id"] == user_alice["id"]

    def test_get_user_by_email_not_found(self, conn):
        assert auth.get_user_by_email(conn, "nobody@example.com") is None

    def test_get_user_by_id(self, conn, user_alice):
        found = auth.get_user_by_id(conn, user_alice["id"])
        assert found is not None
        assert found["email"] == "alice@example.com"

    def test_get_user_by_id_not_found(self, conn):
        assert auth.get_user_by_id(conn, "nonexistent-id") is None

    def test_count_users(self, conn):
        assert auth.count_users(conn) == 0
        auth.create_user(conn, "a@b.com", "A", "password123")
        assert auth.count_users(conn) == 1

    def test_authenticate_success(self, conn, user_alice):
        result = auth.authenticate_user(conn, "alice@example.com", "password123")
        assert result is not None
        assert result["id"] == user_alice["id"]
        assert "password_hash" not in result

    def test_authenticate_wrong_password(self, conn, user_alice):
        result = auth.authenticate_user(conn, "alice@example.com", "wrongpassword")
        assert result is None

    def test_authenticate_nonexistent(self, conn):
        result = auth.authenticate_user(conn, "nobody@example.com", "whatever1")
        assert result is None


# ── Magic links ──

class TestMagicLinks:
    def test_generate_magic_token(self):
        token = auth.generate_magic_token()
        assert len(token) > 20

    def test_create_user_invited(self, conn):
        user = auth.create_user_invited(conn, "invited@example.com", "Invited")
        assert user["email"] == "invited@example.com"
        assert user["magic_token"]
        assert user["is_admin"] is False

    def test_get_user_by_magic_token(self, conn):
        invited = auth.create_user_invited(conn, "magic@example.com", "Magic User")
        found = auth.get_user_by_magic_token(conn, invited["magic_token"])
        assert found is not None
        assert found["id"] == invited["id"]

    def test_get_user_by_magic_token_invalid(self, conn):
        assert auth.get_user_by_magic_token(conn, "nonexistent-token") is None
        assert auth.get_user_by_magic_token(conn, "") is None

    def test_ensure_magic_token_creates(self, conn, user_alice):
        token = auth.ensure_magic_token(conn, user_alice["id"])
        assert token
        # Calling again returns the same token
        token2 = auth.ensure_magic_token(conn, user_alice["id"])
        assert token2 == token

    def test_ensure_magic_token_returns_existing(self, conn):
        invited = auth.create_user_invited(conn, "existing@example.com", "Existing")
        original_token = invited["magic_token"]
        token = auth.ensure_magic_token(conn, invited["id"])
        assert token == original_token

    def test_ensure_magic_token_user_not_found(self, conn):
        with pytest.raises(ValueError, match="User not found"):
            auth.ensure_magic_token(conn, "nonexistent-user-id")

import atexit
from datetime import datetime, timezone
import os
import tempfile
import unittest

from werkzeug.security import generate_password_hash

_TEST_DIR = tempfile.TemporaryDirectory()
atexit.register(_TEST_DIR.cleanup)
os.environ["DATABASE_PATH"] = os.path.join(_TEST_DIR.name, "users.db")

from app import (  # noqa: E402
    app,
    get_db,
    hash_password,
    is_bcrypt_password_hash,
    verify_password,
)


class PasswordVerificationTests(unittest.TestCase):
    def test_bcrypt_password_verifies(self):
        password = "TestPass123!"
        self.assertTrue(verify_password(password, hash_password(password)))
        self.assertFalse(verify_password("WrongPass123!", hash_password(password)))

    def test_legacy_plaintext_password_verifies(self):
        self.assertTrue(verify_password("LegacyPass123!", "LegacyPass123!"))
        self.assertFalse(verify_password("WrongPass123!", "LegacyPass123!"))

    def test_werkzeug_password_hash_verifies(self):
        password = "WerkzeugPass123!"
        self.assertTrue(verify_password(password, generate_password_hash(password)))

    def test_malformed_bcrypt_hash_is_rejected(self):
        self.assertFalse(verify_password("TestPass123!", "$2b$not-a-real-hash"))


class LoginMigrationTests(unittest.TestCase):
    def setUp(self):
        with get_db() as db:
            db.execute("DELETE FROM activity_history")
            db.execute("DELETE FROM users")

    def test_legacy_password_login_upgrades_to_bcrypt(self):
        created_at = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                """
                INSERT INTO users (name, email, password, googleId, profileImage, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Legacy User", "legacy@example.com", "LegacyPass123!", None, None, created_at),
            )

        response = app.test_client().post(
            "/login",
            json={"email": "legacy@example.com", "password": "LegacyPass123!"},
            headers={"Accept": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        with get_db() as db:
            row = db.execute(
                "SELECT password FROM users WHERE email = ?",
                ("legacy@example.com",),
            ).fetchone()

        self.assertTrue(is_bcrypt_password_hash(row["password"]))
        self.assertTrue(verify_password("LegacyPass123!", row["password"]))


class LogoutTests(unittest.TestCase):
    def setUp(self):
        with get_db() as db:
            db.execute("DELETE FROM activity_history")
            db.execute("DELETE FROM users")
            db.execute(
                """
                INSERT INTO users (name, email, password, googleId, profileImage, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Logout User",
                    "logout@example.com",
                    hash_password("LogoutPass123!"),
                    None,
                    None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def test_browser_logout_redirects_to_hero_page(self):
        client = app.test_client()
        client.post(
            "/login",
            json={"email": "logout@example.com", "password": "LogoutPass123!"},
            headers={"Accept": "application/json"},
        )

        response = client.get("/logout", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/#home")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertTrue(
            any(cookie.startswith("auth_token=;") for cookie in response.headers.getlist("Set-Cookie"))
        )

    def test_json_logout_clears_auth_cookie(self):
        client = app.test_client()
        client.post(
            "/login",
            json={"email": "logout@example.com", "password": "LogoutPass123!"},
            headers={"Accept": "application/json"},
        )

        response = client.post("/logout", headers={"Accept": "application/json"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "success")
        self.assertTrue(
            any(cookie.startswith("auth_token=;") for cookie in response.headers.getlist("Set-Cookie"))
        )

    def test_protected_pages_are_not_cached_after_logout(self):
        client = app.test_client()
        with client.session_transaction() as session_data:
            session_data["user"] = "logout@example.com"

        for path in ("/modules", "/dashboard", "/captioning", "/evaluation"):
            with self.subTest(path=path):
                response = client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response.headers["Cache-Control"])


if __name__ == "__main__":
    unittest.main()

from dotenv import load_dotenv
load_dotenv()

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from hmac import compare_digest
import os
import re
import shutil
import sqlite3
import uuid
from urllib.parse import urlencode

import bcrypt
import jwt
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash as check_werkzeug_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "arabic-ai-education-assistant")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

LEGACY_DATABASE_PATH = os.path.join(os.getcwd(), "users.db")


def default_database_path():
    configured_path = os.environ.get("DATABASE_PATH")
    if configured_path:
        return configured_path

    persistent_dir = os.environ.get("PERSISTENT_STORAGE_DIR", "/data")
    if os.path.isdir(persistent_dir) and os.access(persistent_dir, os.W_OK):
        return os.path.join(persistent_dir, "users.db")

    return LEGACY_DATABASE_PATH


DATABASE_PATH = default_database_path()
JWT_SECRET = os.environ.get("JWT_SECRET", app.secret_key)
JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "auth_token"
JWT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
WERKZEUG_PASSWORD_PREFIXES = ("pbkdf2:", "scrypt:")
GOOGLE_CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_REDIRECT_URI = (os.environ.get("GOOGLE_REDIRECT_URI") or "").strip()
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
AUTH_ERROR_MESSAGES = {
    "google_not_configured": (
        "Google sign-in is not configured yet. Add your Google OAuth client ID "
        "to GOOGLE_CLIENT_ID in .env, then restart the app."
    ),
    "google_button_required": "Open the login page and use the Google sign-in button.",
    "google_failed": "Google sign-in failed. Please try again.",
}


@app.after_request
def prevent_auth_page_cache(response):
    if request.path in {"/login", "/signup", "/register", "/google-login", "/google-callback", "/static/google-auth.js"}:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def should_return_json_error():
    return wants_json_response() or request.path.startswith("/api/") or request.path in {"/caption", "/evaluate"}


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    if should_return_json_error():
        return jsonify({"status": "error", "message": error.description or error.name}), error.code

    return error.get_response()


@app.errorhandler(Exception)
def handle_unexpected_exception(error):
    app.logger.exception("Unhandled request error")

    if should_return_json_error():
        return jsonify({"status": "error", "message": "Server error. Please try again."}), 500

    raise error


# ---------------- DATABASE ----------------
def ensure_database_location():
    database_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
    if database_dir:
        os.makedirs(database_dir, exist_ok=True)

    if (
        os.path.abspath(DATABASE_PATH) != os.path.abspath(LEGACY_DATABASE_PATH)
        and not os.path.exists(DATABASE_PATH)
        and os.path.exists(LEGACY_DATABASE_PATH)
    ):
        shutil.copy2(LEGACY_DATABASE_PATH, DATABASE_PATH)


@contextmanager
def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    ensure_database_location()

    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT,
                googleId TEXT UNIQUE,
                profileImage TEXT,
                createdAt TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                subject TEXT,
                details TEXT,
                score REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )


def row_to_user(row):
    if row is None:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "googleId": row["googleId"],
        "profileImage": row["profileImage"],
        "createdAt": row["createdAt"],
    }


def find_user_by_email(email):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return row


def find_user_by_id(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_user(row)


def create_user(name, email, password_hash=None, google_id=None, profile_image=None):
    created_at = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO users (name, email, password, googleId, profileImage, createdAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, password_hash, google_id, profile_image, created_at),
        )
        user_id = cursor.lastrowid

    return find_user_by_id(user_id)


def update_google_user(user_id, name, google_id, profile_image):
    with get_db() as db:
        db.execute(
            """
            UPDATE users
            SET name = COALESCE(NULLIF(?, ''), name),
                googleId = COALESCE(?, googleId),
                profileImage = COALESCE(?, profileImage)
            WHERE id = ?
            """,
            (name, google_id, profile_image, user_id),
        )

    return find_user_by_id(user_id)


def update_user_password(user_id, password_hash):
    with get_db() as db:
        db.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (password_hash, user_id),
        )


# ---------------- AUTH HELPERS ----------------
def wants_json_response():
    return request.is_json or "application/json" in request.headers.get("Accept", "")


def normalize_email(email):
    return (email or "").strip().lower()


def validate_registration(name, email, password, confirm_password):
    errors = []

    if len((name or "").strip()) < 2:
        errors.append("Full name must be at least 2 characters.")

    if not EMAIL_PATTERN.match(email or ""):
        errors.append("Enter a valid email address.")

    if len(password or "") < 8:
        errors.append("Password must be at least 8 characters.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    existing_user = find_user_by_email(email)
    if existing_user:
        if existing_user["googleId"] and not existing_user["password"]:
            errors.append(
                "An account with this email already exists using Google sign-in. "
                "Please sign in with Google or use password reset."
            )
        else:
            errors.append("An account with this email already exists.")

    return errors


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def is_bcrypt_password_hash(password_hash):
    return (password_hash or "").startswith(BCRYPT_PREFIXES)


def password_needs_rehash(password_hash):
    return bool(password_hash) and not is_bcrypt_password_hash(password_hash)


def verify_password(password, password_hash):
    if not password_hash:
        return False

    if is_bcrypt_password_hash(password_hash):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    if password_hash.startswith(WERKZEUG_PASSWORD_PREFIXES):
        try:
            return check_werkzeug_password_hash(password_hash, password)
        except (TypeError, ValueError):
            return False

    return compare_digest(password_hash, password)


def upgrade_password_hash_if_needed(user_id, password, password_hash):
    if password_needs_rehash(password_hash):
        update_user_password(user_id, hash_password(password))


def create_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_MAX_AGE_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _format_feedback_terms(items, limit=3):
    terms = [str(item).replace("_", " ").strip() for item in (items or []) if str(item).strip()]
    if not terms:
        return ""
    return ", ".join(terms[:limit])


def build_ai_feedback(result):
    score_val = int(result.get("score", 0) or 0)
    relevance_val = float(result.get("question_relevance", 0.0) or 0.0)
    concept_val = float(result.get("concept_match", result.get("coverage", 0.0)) or 0.0)
    matched = result.get("matched_concepts", []) or []
    missing = result.get("missing_reference_concepts", []) or []
    extra = result.get("extra_student_concepts", []) or []

    if relevance_val < 0.35:
        first = "The response is mostly off-topic and does not address the question in a clear way."
    elif score_val >= 8:
        first = "The response is on-topic and shows a strong understanding of the main ideas in the reference answer."
    elif score_val >= 5:
        first = "The response is on-topic and shows partial understanding, but its coverage of the reference answer is incomplete."
    else:
        first = "The response shows limited understanding of the reference answer and only weakly supports the question."

    strengths = _format_feedback_terms(matched, limit=2)
    missing_terms = _format_feedback_terms(missing, limit=3)
    extra_terms = _format_feedback_terms(extra, limit=2)

    if strengths and missing_terms:
        second = (
            f"It correctly touches on {strengths}, but key concepts such as {missing_terms} are missing or not clearly explained"
        )
    elif strengths:
        second = f"It correctly addresses concepts such as {strengths}"
    elif missing_terms:
        second = f"Key concepts such as {missing_terms} are missing or not clearly explained"
    else:
        second = "The response shows limited evidence of the key concepts expected in the reference answer"

    if extra_terms and (relevance_val < 0.6 or concept_val < 0.45):
        second += ", and it includes off-target content that is not supported by the reference answer."
    else:
        second += "."

    if relevance_val < 0.35:
        third = "To improve, answer the question directly first and then include the main reference concepts."
    elif concept_val < 0.25:
        third = "To improve, focus on the main reference concepts and explain them more directly."
    elif concept_val < 0.55:
        third = "To improve, add the missing key concepts and support them with clearer detail."
    else:
        third = "To improve, make the explanation slightly more complete and precise."

    return " ".join([first, second, third])


def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

    return find_user_by_id(payload.get("sub"))


def request_auth_token():
    token = request.cookies.get(JWT_COOKIE_NAME) or request.args.get(JWT_COOKIE_NAME)
    authorization = request.headers.get("Authorization", "")

    if not token and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

    if not token:
        token = (request.headers.get("X-Auth-Token") or "").strip()

    if not token and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            token = request.form.get(JWT_COOKIE_NAME) or request.form.get("auth_token")
        except Exception:
            token = None

    if not token and request.is_json:
        data = request.get_json(silent=True) or {}
        token = data.get(JWT_COOKIE_NAME) or data.get("auth_token")

    return token


def current_user():
    token = request_auth_token()

    if token:
        user = decode_token(token)
        if user:
            return user

    session_email = normalize_email(session.get("user"))
    if session_email:
        return row_to_user(find_user_by_email(session_email))

    return None


def page_auth_token(user):
    return create_token(user)


def cookie_secure():
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    forwarded_proto = forwarded_proto.split(",")[0].strip().lower()
    return request.is_secure or forwarded_proto == "https"


def cookie_samesite():
    return "None" if cookie_secure() else "Lax"


def set_auth_cookie(response, token):
    response.set_cookie(
        JWT_COOKIE_NAME,
        token,
        max_age=JWT_MAX_AGE_SECONDS,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(JWT_COOKIE_NAME)
    return response


def auth_success_response(user, message="Signed in successfully."):
    token = create_token(user)

    if wants_json_response():
        response = jsonify({"status": "success", "message": message, "token": token, "user": user})
    else:
        response = redirect(url_for("modules"))

    session["user"] = user["email"]
    return set_auth_cookie(response, token)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user:
            return view(user, *args, **kwargs)

        if wants_json_response():
            return jsonify({"status": "error", "message": "Authentication required."}), 401

        return redirect(url_for("login"))

    return wrapped


def request_data():
    return (request.get_json(silent=True) or {}) if request.is_json else request.form


def auth_error_message():
    return AUTH_ERROR_MESSAGES.get(request.args.get("error"))


def google_signin_nonce():
    if not GOOGLE_CLIENT_ID:
        return ""

    nonce = uuid.uuid4().hex
    session["google_oauth_nonce"] = nonce
    return nonce


def google_callback_url():
    if GOOGLE_REDIRECT_URI:
        return GOOGLE_REDIRECT_URI

    return url_for("google_callback", _external=True)


def caption_image(file):
    from src.image_captioning.pipeline import generate_caption
    from src.image_captioning.translator import translate_to_arabic

    filename = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    english_caption = generate_caption(path)
    arabic_caption = translate_to_arabic(english_caption)

    # Generate a confidence score based on caption length and content
    confidence = min(95, max(60, 70 + len(english_caption.split()) * 2))

    return {
        "filename": filename,
        "image_url": url_for("static", filename=f"uploads/{filename}"),
        "english_caption": english_caption,
        "arabic_caption": arabic_caption,
        "confidence": confidence,
    }


def log_activity(user_id, activity_type, subject=None, details=None, score=None):
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO activity_history (user_id, activity_type, subject, details, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, activity_type, subject, details, score, created_at),
        )


def get_user_stats(user_id):
    with get_db() as db:
        captions = db.execute(
            "SELECT COUNT(*) as cnt FROM activity_history WHERE user_id = ? AND activity_type = 'caption'",
            (user_id,),
        ).fetchone()["cnt"]
        evaluations = db.execute(
            "SELECT COUNT(*) as cnt FROM activity_history WHERE user_id = ? AND activity_type = 'evaluation'",
            (user_id,),
        ).fetchone()["cnt"]
        avg_score = db.execute(
            "SELECT AVG(score) as avg_score FROM activity_history WHERE user_id = ? AND activity_type = 'evaluation' AND score IS NOT NULL",
            (user_id,),
        ).fetchone()["avg_score"]
    return {
        "images_processed": captions,
        "answers_evaluated": evaluations,
        "ai_accuracy": round(avg_score * 10, 1) if avg_score else 0,
    }


def get_user_history(user_id, limit=20):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT id, activity_type, subject, details, score, created_at
            FROM activity_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["activity_type"],
            "subject": row["subject"],
            "details": row["details"],
            "score": row["score"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# ---------------- PAGES ----------------
@app.route("/")
def home():
    if current_user():
        return redirect(url_for("modules"))

    return render_template("hero.html", google_client_id=GOOGLE_CLIENT_ID)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template(
            "signup.html",
            google_client_id=GOOGLE_CLIENT_ID,
            google_nonce=google_signin_nonce(),
            error=auth_error_message(),
        )

    data = request_data()
    name = (data.get("name") or "").strip()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or data.get("confirmPassword")
    if confirm_password is None:
        confirm_password = password

    errors = validate_registration(name, email, password, confirm_password)
    if errors:
        if wants_json_response():
            return jsonify({"status": "error", "message": errors[0], "errors": errors}), 400

        return render_template(
            "signup.html",
            error=errors[0],
            form={"name": name, "email": email},
            google_client_id=GOOGLE_CLIENT_ID,
            google_nonce=google_signin_nonce(),
        ), 400

    user = create_user(name, email, hash_password(password))
    return auth_success_response(user, "Account created successfully.")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Alias for /register - for modern UI compatibility"""
    return register()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template(
            "login.html",
            google_client_id=GOOGLE_CLIENT_ID,
            google_nonce=google_signin_nonce(),
            error=auth_error_message(),
        )

    data = request_data()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    row = find_user_by_email(email)

    if row and not row["password"] and row["googleId"]:
        message = "This account uses Google sign-in. Please sign in with Google or reset your password."
    elif not row or not verify_password(password, row["password"]):
        message = "Invalid email or password."
    else:
        upgrade_password_hash_if_needed(row["id"], password, row["password"])
        return auth_success_response(row_to_user(row), "Welcome back.")

    if wants_json_response():
        return jsonify({"status": "error", "message": message}), 401

    return render_template(
        "login.html",
        error=message,
        form={"email": email},
        google_client_id=GOOGLE_CLIENT_ID,
        google_nonce=google_signin_nonce(),
    ), 401


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        return render_template("reset_password.html")

    email = normalize_email(request_data().get("email"))
    message = "If an account exists for that email, password reset instructions will be sent."

    if wants_json_response():
        return jsonify({"status": "success", "message": message, "email": email})

    return render_template("reset_password.html", success=message, email=email)


@app.route("/google-login", methods=["GET", "POST"])
def google_login():
    if not GOOGLE_CLIENT_ID:
        if wants_json_response():
            return jsonify({"status": "error", "message": "Google login is not configured."}), 503
        return redirect(url_for("login", error="google_not_configured"))

    if request.method == "GET":
        nonce = uuid.uuid4().hex
        state = uuid.uuid4().hex
        session["google_oauth_nonce"] = nonce
        session["google_oauth_state"] = state

        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": google_callback_url(),
            "response_type": "id_token",
            "scope": "openid email profile",
            "nonce": nonce,
            "state": state,
            "prompt": "select_account",
        }
        return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))

    # Handle POST: credential from the Google account chooser callback.
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()
    credential = data.get("credential") or data.get("id_token") or request.form.get("credential") or request.form.get("id_token")
    if not credential:
        return jsonify({"status": "error", "message": "Missing Google credential."}), 400
    expected_nonce = session.pop("google_oauth_nonce", None)
    expected_state = session.pop("google_oauth_state", None)
    received_state = data.get("state") or request.form.get("state")
    if not expected_nonce or not expected_state or received_state != expected_state:
        return jsonify({"status": "error", "message": "Google sign-in session expired. Please try again."}), 401

    try:
        profile = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid Google credential."}), 401

    if profile.get("nonce") != expected_nonce:
        return jsonify({"status": "error", "message": "Invalid Google sign-in session."}), 401

    email = normalize_email(profile.get("email"))
    google_id = profile.get("sub")
    name = profile.get("name") or email.split("@")[0]
    profile_image = profile.get("picture")

    if not email or not google_id:
        return jsonify({"status": "error", "message": "Google profile is missing required information."}), 400

    email_verified = profile.get("email_verified")
    if email_verified is not True and str(email_verified).lower() != "true":
        return jsonify({"status": "error", "message": "Google email address is not verified."}), 401

    existing = find_user_by_email(email)
    if existing:
        user = update_google_user(existing["id"], name, google_id, profile_image)
    else:
        user = create_user(name, email, google_id=google_id, profile_image=profile_image)

    return auth_success_response(user, "Signed in with Google.")


@app.route("/google-callback")
def google_callback():
    return render_template("google_callback.html", google_client_id=GOOGLE_CLIENT_ID)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()

    if wants_json_response():
        response = jsonify({"status": "success", "message": "Signed out."})
    else:
        response = redirect(url_for("home"))

    return clear_auth_cookie(response)


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard(user):
    return render_template("dashboard.html", user=user, auth_token=page_auth_token(user))


@app.route("/modules")
@login_required
def modules(user):
    return render_template("dashboard.html", user=user, auth_token=page_auth_token(user))


# ---------------- IMAGE CAPTIONING PAGE ----------------
@app.route("/captioning", methods=["GET"])
@login_required
def captioning_page(user):
    return render_template("captioning.html", user=user, auth_token=page_auth_token(user))


# ---------------- ANSWER EVALUATION PAGE ----------------
@app.route("/evaluation", methods=["GET"])
@login_required
def evaluation_page(user):
    return render_template("evaluation.html", user=user, auth_token=page_auth_token(user))


# ---------------- IMAGE CAPTIONING ----------------
@app.route("/upload", methods=["POST"])
@login_required
def upload(user):
    file = request.files.get("image")
    if not file:
        return render_template(
            "captioning.html",
            user=user,
            auth_token=page_auth_token(user),
            caption_error="Choose an image first.",
        ), 400

    result = caption_image(file)
    log_activity(user["id"], "caption", details=result.get("english_caption", ""))
    return render_template("captioning.html", user=user, auth_token=page_auth_token(user), caption_result=result)


@app.route("/caption", methods=["POST"])
@login_required
def caption(user):
    file = request.files.get("image")
    if not file:
        return jsonify({"status": "error", "message": "Choose an image first."}), 400

    try:
        result = caption_image(file)
    except Exception:
        return jsonify({"status": "error", "message": "Failed to generate caption. Please try again."}), 500

    log_activity(user["id"], "caption", details=result.get("english_caption", ""))
    return jsonify(result)


# ---------------- ANSWER EVALUATION ----------------
@app.route("/evaluate", methods=["POST"])
@login_required
def evaluate(user):
    if request.is_json:
        data = request.get_json(silent=True) or {}
        reference = data.get("reference_answer") or data.get("reference")
        student = data.get("student_answer") or data.get("student")
        subject = data.get("subject", "General")
    else:
        reference = request.form.get("reference")
        student = request.form.get("student")
        subject = request.form.get("subject", "General")

    from src.answer_evaluation.evaluator import evaluate_answer

    result = evaluate_answer(subject, reference, student)

    # Generate enhanced feedback based on score
    score_val = result.get("score", 0)
    similarity_val = result.get("similarity", 0)
    relevance_val = result.get("question_relevance", 1.0)
    concept_val = result.get("concept_match", result.get("coverage", 0))

    if relevance_val < 0.35:
        feedback = {
            "correct_concepts": ["The response was checked against the reference answer"],
            "missing_concepts": ["The answer does not clearly address the question", "Important question-specific ideas are missing"],
            "suggestions": ["Rewrite the response so it directly answers the question", "Use key terms from the question and connect them to the reference answer"],
        }
    elif concept_val < 0.25:
        feedback = {
            "correct_concepts": ["The response attempts the topic"],
            "missing_concepts": ["Most key concepts from the reference answer are missing", "The answer needs stronger concept coverage"],
            "suggestions": ["Use the main ideas from the reference answer", "Include the essential terms and explain them directly"],
        }
    elif score_val >= 8:
        feedback = {
            "correct_concepts": ["Core concepts understood", "Good knowledge demonstration"],
            "missing_concepts": ["Minor details could be added"],
            "suggestions": ["Try to include more specific examples", "Review advanced topics for completeness"],
        }
    elif score_val >= 5:
        feedback = {
            "correct_concepts": ["Basic understanding shown", "Some key points covered"],
            "missing_concepts": ["Several important concepts missing", "Lacks detailed explanations"],
            "suggestions": ["Review the reference material more carefully", "Focus on key terminology", "Add supporting details"],
        }
    else:
        feedback = {
            "correct_concepts": ["Attempted to address the topic"],
            "missing_concepts": ["Most key concepts are missing", "Significant gaps in understanding"],
            "suggestions": ["Study the reference answer thoroughly", "Break down the topic into smaller parts", "Seek additional resources or ask for help"],
        }

    if relevance_val < 0.6 and relevance_val >= 0.35:
        feedback["missing_concepts"].insert(0, "The answer is only partly relevant to the question")
        feedback["suggestions"].insert(0, "Tie the answer more directly to the question prompt")

    if concept_val < 0.45 and relevance_val >= 0.35:
        feedback["missing_concepts"].insert(0, "Several reference-answer concepts are missing")
        feedback["suggestions"].insert(0, "Cover more of the key concepts from the reference answer")

    result["feedback"] = feedback
    result["ai_feedback"] = build_ai_feedback(result)
    result["subject"] = subject
    result["score_percentage"] = score_val * 10

    log_activity(user["id"], "evaluation", subject=subject, score=score_val)

    if request.is_json:
        return jsonify(result)

    return render_template(
        "evaluation.html",
        user=user,
        auth_token=page_auth_token(user),
        evaluation_result=result,
        reference_answer=reference,
        student_answer=student,
    )


# ---------------- STATS & HISTORY API ----------------
@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats(user):
    stats = get_user_stats(user["id"])
    return jsonify(stats)


@app.route("/api/history", methods=["GET"])
@login_required
def api_history(user):
    history = get_user_history(user["id"])
    return jsonify(history)


# ---------------- DASHBOARD MODULE CONTENT APIS ----------------
@app.route("/api/module/captioning", methods=["GET"])
@login_required
def api_module_captioning(user):
    """Fetch Image Captioning module content for dashboard"""
    return render_template("module_captioning.html", user=user)


@app.route("/api/module/evaluation", methods=["GET"])
@login_required
def api_module_evaluation(user):
    """Fetch Answer Evaluation module content for dashboard"""
    return render_template("module_evaluation.html", user=user)


init_db()


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port)

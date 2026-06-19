from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import os
import re
import sqlite3
import uuid
from urllib.parse import urlencode

import bcrypt
import jwt
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "arabic-ai-education-assistant")

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.getcwd(), "users.db"))
JWT_SECRET = os.environ.get("JWT_SECRET", app.secret_key)
JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "auth_token"
JWT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
GOOGLE_CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
AUTH_ERROR_MESSAGES = {
    "google_not_configured": (
        "Google sign-in is not configured yet. Add your Google OAuth client ID "
        "to GOOGLE_CLIENT_ID in .env, then restart the app."
    ),
}


@app.after_request
def prevent_auth_page_cache(response):
    if request.path in {"/login", "/signup", "/register", "/google-login", "/google-callback"}:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------------- DATABASE ----------------
def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
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


def verify_password(password, password_hash):
    if not password_hash:
        return False

    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


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


def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

    return find_user_by_id(payload.get("sub"))


def current_user():
    token = request.cookies.get(JWT_COOKIE_NAME)
    authorization = request.headers.get("Authorization", "")

    if not token and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

    if not token:
        return None

    return decode_token(token)


def cookie_secure():
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    return forwarded_proto == "https"


def set_auth_cookie(response, token):
    response.set_cookie(
        JWT_COOKIE_NAME,
        token,
        max_age=JWT_MAX_AGE_SECONDS,
        httponly=True,
        secure=cookie_secure(),
        samesite="Lax",
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
        response = redirect(url_for("dashboard"))

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
        return redirect(url_for("dashboard"))

    return render_template("hero.html", google_client_id=GOOGLE_CLIENT_ID)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("signup.html", google_client_id=GOOGLE_CLIENT_ID, error=auth_error_message())

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
        return render_template("login.html", google_client_id=GOOGLE_CLIENT_ID, error=auth_error_message())

    data = request_data()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    row = find_user_by_email(email)

    if row and not row["password"] and row["googleId"]:
        message = "This account uses Google sign-in. Please sign in with Google or reset your password."
    elif not row or not verify_password(password, row["password"]):
        message = "Invalid email or password."
    else:
        return auth_success_response(row_to_user(row), "Welcome back.")

    if wants_json_response():
        return jsonify({"status": "error", "message": message}), 401

    return render_template(
        "login.html",
        error=message,
        form={"email": email},
        google_client_id=GOOGLE_CLIENT_ID,
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
        session["google_oauth_nonce"] = nonce
        callback_url = url_for("google_callback", _external=True)
        if request.headers.get("X-Forwarded-Proto") == "https":
            callback_url = callback_url.replace("http://", "https://", 1)
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": callback_url,
            "response_type": "id_token",
            "scope": "openid email profile",
            "nonce": nonce,
            "prompt": "select_account",
        }
        return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))

    # Handle POST: credential from the Google callback page.
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()
    credential = data.get("credential") or data.get("id_token") or request.form.get("credential") or request.form.get("id_token")
    if not credential:
        return jsonify({"status": "error", "message": "Missing Google credential."}), 400

    try:
        profile = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid Google credential."}), 401

    email = normalize_email(profile.get("email"))
    google_id = profile.get("sub")
    name = profile.get("name") or email.split("@")[0]
    profile_image = profile.get("picture")

    if not email or not google_id:
        return jsonify({"status": "error", "message": "Google profile is missing required information."}), 400

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
        response = redirect(url_for("login"))

    return clear_auth_cookie(response)


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard(user):
    return render_template("dashboard.html", user=user)


# ---------------- IMAGE CAPTIONING PAGE ----------------
@app.route("/captioning", methods=["GET"])
@login_required
def captioning_page(user):
    return render_template("captioning.html", user=user)


# ---------------- ANSWER EVALUATION PAGE ----------------
@app.route("/evaluation", methods=["GET"])
@login_required
def evaluation_page(user):
    return render_template("evaluation.html", user=user)


# ---------------- IMAGE CAPTIONING ----------------
@app.route("/upload", methods=["POST"])
@login_required
def upload(user):
    file = request.files.get("image")
    if not file:
        return render_template(
            "captioning.html",
            user=user,
            caption_error="Choose an image first.",
        ), 400

    result = caption_image(file)
    log_activity(user["id"], "caption", details=result.get("english_caption", ""))
    return render_template("captioning.html", user=user, caption_result=result)


@app.route("/caption", methods=["POST"])
@login_required
def caption(user):
    file = request.files.get("image")
    if not file:
        return jsonify({"status": "error", "message": "Choose an image first."}), 400

    result = caption_image(file)
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

    result = evaluate_answer(reference, student)

    # Generate enhanced feedback based on score
    score_val = result.get("score", 0)
    similarity_val = result.get("similarity", 0)

    if score_val >= 8:
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

    result["feedback"] = feedback
    result["subject"] = subject
    result["score_percentage"] = score_val * 10

    log_activity(user["id"], "evaluation", subject=subject, score=score_val)

    if request.is_json:
        return jsonify(result)

    return render_template(
        "evaluation.html",
        user=user,
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

---
title: Arabic AI Education Assistant
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_file: app.py
pinned: false
---

# Arabic AI Education Assistant

## 🧠 Overview
This is a Flask-based AI backend system for Arabic education tasks including image captioning and answer evaluation. It is deployed using Docker on Hugging Face Spaces.

---

## 🚀 Features

### 📸 Image Captioning
- Upload an image
- Generates English caption
- Translates caption into Arabic

### 📝 Answer Evaluation
- Compares student answer with reference answer
- Returns similarity score and final grade

### 🔐 Login API
- Simple authentication system (demo purpose)

---

## ⚙️ Tech Stack

- Flask
- Docker
- PyTorch / Transformers
- Sentence Transformers
- NLP + Computer Vision models

---

## Google Sign-In Setup

Google sign-in is disabled until you configure your own OAuth client ID. The app
uses the Google Identity Services button, so create a Google OAuth Web client,
then add this to `.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

For local development, add these Authorized JavaScript origins to that Google
client:

```text
http://localhost:7860
http://127.0.0.1:7860
```

For Hugging Face or another deployed host, add your deployed app origin:

```text
https://derlinshaju2-arabic-ai-education-assistant.hf.space
```

No redirect URI is required for the default Google button flow.

If Google shows a 403 access page, check the OAuth consent screen: an Internal
app only works for accounts in its organization, and a Testing app only works
for listed test users.

---
title: IntelliArabic
emoji: 🧠
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Arabic AI captions and answer scoring.
models:
  - Salesforce/blip-image-captioning-base
  - Helsinki-NLP/opus-mt-en-ar
  - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
tags:
  - flask
  - docker
  - arabic
  - education
  - image-captioning
  - answer-evaluation
---

# IntelliArabic – Arabic AI Education Assistant

An AI-powered educational web application that combines **Computer Vision** and **Natural Language Processing** to support Arabic language learning.

The application provides two main modules:

1. **Arabic Image Captioning**
2. **Automated Arabic Answer Evaluation**

---

## Live Demo

**Hugging Face Space:**
https://derlinshaju2-arabic-ai-education-assistant.hf.space/

**GitHub Repository:**
https://github.com/derlinshaju2/Arabic_AI_Education_Assistant

---

## Project Overview

IntelliArabic helps users understand images and evaluate Arabic answers using modern deep-learning and transformer-based models.

The system can:

* Generate an English description for an uploaded image.
* Translate the generated English caption into Arabic.
* Compare a student's Arabic answer with a reference answer.
* Calculate semantic similarity.
* Generate a score out of 10.

---

## Main Features

### 1. Image Captioning

Users can upload an image in JPG, PNG, WebP, or GIF format.

The system:

* Processes the uploaded image.
* Identifies the main objects, people, actions, and environment.
* Generates an English caption.
* Translates the caption into Arabic.
* Displays the uploaded image and both captions.
* Allows users to copy or regenerate the results.

### 2. Answer Evaluation

Users provide:

* A question
* A reference answer
* A student answer

The system then:

* Preprocesses the Arabic text.
* Generates multilingual sentence embeddings.
* Calculates semantic similarity using cosine similarity.
* Predicts a score out of 10.

---

## Technologies Used

### Backend

* Python
* Flask
* Gunicorn

### Artificial Intelligence

* PyTorch
* Hugging Face Transformers
* BLIP Image Captioning
* MarianMT English-to-Arabic Translation
* Sentence Transformers
* Cosine Similarity

### Frontend

* HTML5
* CSS3
* JavaScript
* Responsive dashboard interface

### Deployment

* Docker
* Hugging Face Spaces
* GitHub

---

## AI Models

### Image Captioning

```text
Salesforce/blip-image-captioning-base
```

The BLIP model analyzes an uploaded image and generates an English description.

### English-to-Arabic Translation

```text
Helsinki-NLP/opus-mt-en-ar
```

The generated English caption is translated into Arabic using MarianMT.

### Arabic Answer Evaluation

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

The model creates semantic embeddings for the reference answer and student answer.

Cosine similarity is used to measure how closely the two answers match.

---

## System Architecture

```text
User
  │
  ▼
Flask Web Application
  │
  ├── Image Captioning Module
  │     ├── Image Upload
  │     ├── BLIP Caption Generation
  │     ├── English Caption
  │     ├── MarianMT Translation
  │     └── Arabic Caption
  │
  └── Answer Evaluation Module
        ├── Arabic Text Input
        ├── Text Preprocessing
        ├── Sentence Embeddings
        ├── Cosine Similarity
        ├── Score Prediction
        └── Feedback Generation
```

---

## Project Structure


```text
Arabic_AI_Education_Assistant/
│
├── src/
│   ├── answer_evaluation/
│   │   ├── __init__.py
│   │   ├── evaluate.py
│   │   ├── evaluator.py
│   │   ├── preprocess.py
│   │   ├── scoring.py
│   │   ├── similarity.py
│   │   └── vectorizer.py
│   │
│   ├── image_captioning/
│   │   ├── app.py
│   │   ├── caption_generator.py
│   │   ├── feature_extractor.py
│   │   ├── pipeline.py
│   │   ├── preprocess_dataset.py
│   │   ├── train_model.py
│   │   └── translator.py
│   │
│   ├── __init__.py
│   └── app.py
│
├── static/
│   ├── arabic.png
│   ├── captioning-layout.css
│   ├── dashboard-module-overrides.css
│   ├── google-auth.js
│   ├── hero-mobile-menu.css
│   ├── hero.css
│   ├── mobile-module-fix.css
│   ├── mobile-module-fix.js
│   ├── script.js
│   └── style.css
│
├── templates/
│   ├── dashboard.html
│   ├── captioning.html
│   ├── evaluation.html
│   ├── module_captioning.html
│   ├── module_evaluation.html
│   ├── login.html
│   ├── signup.html
│   └── hero.html
│
├── .gitattributes
├── .gitignore
├── Dockerfile
├── Procfile
├── README.md
├── __init__.py
├── app.py
├── render.yaml
├── requirements.txt
├── runtime.txt
├── test_answer_evaluation.py
├── test_auth.py
└── test_captioning.py
```

### Important Files

* `app.py` – Main Flask application and API routes.
* `src/image_captioning/pipeline.py` – Image-caption generation pipeline.
* `src/image_captioning/translator.py` – English-to-Arabic caption translation.
* `src/answer_evaluation/evaluator.py` – Main answer-evaluation workflow.
* `src/answer_evaluation/similarity.py` – Semantic-similarity calculation.
* `src/answer_evaluation/scoring.py` – Converts similarity into a score.
* `templates/` – Flask HTML pages and dynamically loaded modules.
* `static/` – CSS, JavaScript, images, and responsive layout files.
* `Dockerfile` – Docker configuration for Hugging Face Spaces.
* `requirements.txt` – Required Python libraries.
* `test_captioning.py` – Tests for image captioning.
* `test_answer_evaluation.py` – Tests for answer evaluation.
* `test_auth.py` – Tests for authentication.

---

## Answer Evaluation Workflow

```text
Question
   +
Reference Answer
   +
Student Answer
        │
        ▼
Arabic Text Preprocessing
        │
        ▼
Sentence Embedding Generation
        │
        ▼
Cosine Similarity Calculation
        │
        ▼
Score Prediction
        │
        ▼
Feedback and Recommendations
```

---

## Score Mapping

The semantic similarity value is converted into a score out of 10.

| Similarity     | Score |
| -------------- | ----: |
| 0.95 and above |    10 |
| 0.85–0.94      |     9 |
| 0.75–0.84      |     8 |
| 0.65–0.74      |     7 |
| 0.55–0.64      |     6 |
| 0.45–0.54      |     5 |
| 0.35–0.44      |     4 |
| 0.25–0.34      |     3 |
| 0.15–0.24      |     2 |
| Below 0.15     |     0 |

---

## Example Answer Evaluation

### Question

```text
ما هي فوائد الماء لجسم الإنسان؟
```

### Reference Answer

```text
الماء ضروري لجسم الإنسان لأنه ينظم درجة حرارة الجسم ويساعد على الهضم ويطرد السموم ويحافظ على ترطيب الجسم.
```

### Student Answer

```text
الماء مهم للجسم لأنه يساعد على تنظيم درجة الحرارة وتحسين الهضم والتخلص من السموم والمحافظة على ترطيب الجسم.
```

### Expected Result

```text
Similarity: Approximately 90%–97%
Score: 9–10/10
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/derlinshaju2/Arabic_AI_Education_Assistant.git
```

### 2. Open the project folder

```bash
cd Arabic_AI_Education_Assistant
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the environment

#### Windows

```powershell
venv\Scripts\activate
```

#### Linux or macOS

```bash
source venv/bin/activate
```

### 5. Install the dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Flask application

```bash
python app.py
---

## Docker Setup

### Build the Docker image

```bash
docker build -t intelliarabic .
```

### Run the container

```bash
docker run -p 7860:7860 intelliarabic
```

---

## Application Pages

| Route                    | Description                       |
| ------------------------ | --------------------------------- |
| `/`                      | Landing or login page             |
| `/dashboard`             | Main dashboard                    |
| `/captioning`            | Standalone image-captioning page  |
| `/evaluation`            | Standalone answer-evaluation page |
| `/api/module/captioning` | Dynamic captioning module         |
| `/api/module/evaluation` | Dynamic evaluation module         |
| `/caption`               | Image-captioning API              |
| `/evaluate`              | Answer-evaluation API             |

---

## Responsive Design

The interface is optimized for:

* Desktop computers
* Laptops
* Tablets
* Mobile devices

The dashboard includes:

* Collapsible sidebar
* Responsive two-column workspace
* Mobile stacked layout
* Shared module button components
* Image previews
* Loading indicators
* Copy and regenerate actions

---

## Current Limitations

* Image-caption accuracy depends on the pretrained vision model.
* Complex or unusual images may produce generic or partially incorrect descriptions.
* Arabic translation quality depends on the generated English caption.
* Similarity scores represent semantic closeness and may not always match human grading exactly.
* Large AI models can increase application startup time and memory usage.


## Future Improvements

* Upgrade to a stronger vision-language model.
* Generate multiple caption candidates and rank them using CLIP.
* Improve detailed object and activity recognition.
* Add grammar correction before translation.
* Add confidence scores for generated captions.
* Improve Arabic educational feedback.
* Add teacher and student accounts.
* Store evaluation and caption history.
* Export evaluation reports as PDF.
* Add more Arabic dialect support.
* Add multilingual question and answer evaluation.

---

## Author

**Derlin Shaju**

B.Tech in Artificial Intelligence and Data Science

* GitHub: https://github.com/derlinshaju2
* Hugging Face: https://huggingface.co/derlinshaju2

---


## Acknowledgements

* Hugging Face
* Salesforce BLIP
* Helsinki-NLP
* Sentence Transformers
* PyTorch
* Flask
* Docker

---

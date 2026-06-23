from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.scoring import generate_score
from src.answer_evaluation.similarity import calculate_similarity


QUESTION_STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "briefly", "define", "describe",
    "answer", "because", "did", "do", "does", "explain", "for", "from", "give", "help",
    "helps", "how", "identify", "important",
    "in", "into", "is", "list", "mention", "of", "on", "or", "the", "to",
    "response", "student", "supports", "using", "used", "was", "were", "what",
    "when", "where", "which", "who", "why", "with",
}

GENERIC_QUESTIONS = {"", "general", "question", "topic", "arabic", "science", "history", "math"}
ARABIC_STOPWORDS = {
    "\u0627\u0646", "\u0627\u0648", "\u0627\u064a", "\u0628\u0647", "\u0628\u064a\u0646",
    "\u062d\u0648\u0644", "\u062e\u0644\u0627\u0644", "\u062f\u0648\u0646", "\u0639\u0644\u0649",
    "\u0639\u0646", "\u0641\u064a", "\u0643\u0627\u0646", "\u0644\u0627", "\u0644\u0642\u062f",
    "\u0644\u0645", "\u0644\u0646", "\u0645\u0627", "\u0645\u0639", "\u0645\u0646",
    "\u0647\u0630\u0627", "\u0647\u0630\u0647", "\u0647\u0648", "\u0647\u064a", "\u0648",
}
MIN_CONTENT_TOKENS = 2


def _clamp(value):
    return max(0.0, min(1.0, float(value or 0.0)))


def _content_tokens(text):
    normalized = preprocess_text(text).lower()
    return {
        token
        for token in normalized.split()
        if len(token) > MIN_CONTENT_TOKENS
        and token not in QUESTION_STOPWORDS
        and token not in ARABIC_STOPWORDS
        and not token.isdigit()
    }


def _token_overlap(source_text, target_text):
    source_tokens = _content_tokens(source_text)
    target_tokens = _content_tokens(target_text)

    if not source_tokens or not target_tokens:
        return {
            "source_tokens": source_tokens,
            "target_tokens": target_tokens,
            "shared_tokens": set(),
            "recall": 0.0,
            "precision": 0.0,
            "f1": 0.0,
        }

    shared_tokens = source_tokens & target_tokens
    recall = len(shared_tokens) / len(source_tokens)
    precision = len(shared_tokens) / len(target_tokens)
    if recall + precision == 0:
        f1 = 0.0
    else:
        f1 = (2 * recall * precision) / (recall + precision)

    return {
        "source_tokens": source_tokens,
        "target_tokens": target_tokens,
        "shared_tokens": shared_tokens,
        "recall": recall,
        "precision": precision,
        "f1": f1,
    }


def _keyword_overlap(source_text, target_text):
    overlap = _token_overlap(source_text, target_text)
    return _clamp((overlap["recall"] * 0.65) + (overlap["precision"] * 0.35))


def _question_is_generic(question):
    return (question or "").strip().lower() in GENERIC_QUESTIONS


def calculate_concept_match(reference_answer, student_answer):
    reference_clean = preprocess_text(reference_answer)
    student_clean = preprocess_text(student_answer)
    overlap = _token_overlap(reference_clean, student_clean)
    concept_match = _clamp((overlap["recall"] * 0.7) + (overlap["precision"] * 0.3))
    return concept_match, overlap


def calculate_question_relevance(question, student_answer):
    if _question_is_generic(question):
        return 1.0

    question_clean = preprocess_text(question)
    student_clean = preprocess_text(student_answer)

    if not question_clean or not student_clean:
        return 0.0

    semantic_relevance = _clamp(calculate_similarity(question_clean, student_clean))
    overlap = _token_overlap(question_clean, student_clean)
    keyword_relevance = _clamp((overlap["recall"] * 0.6) + (overlap["precision"] * 0.4))

    if not overlap["shared_tokens"]:
        semantic_relevance *= 0.45
    elif keyword_relevance < 0.2:
        semantic_relevance *= 0.7

    return _clamp((semantic_relevance * 0.55) + (keyword_relevance * 0.45))


def combine_similarity_metrics(reference_similarity, concept_match):
    adjusted_semantic = _clamp(reference_similarity)

    if concept_match < 0.12:
        adjusted_semantic *= 0.35
    elif concept_match < 0.25:
        adjusted_semantic *= 0.6
    elif concept_match < 0.4:
        adjusted_semantic *= 0.8

    combined = (adjusted_semantic * 0.55) + (concept_match * 0.45)
    return _clamp(combined)


def combine_evaluation_score(answer_similarity, concept_match, question_relevance):
    combined = (
        (answer_similarity * 0.5) +
        (concept_match * 0.3) +
        (question_relevance * 0.2)
    )

    if question_relevance < 0.2:
        combined = min(combined, 0.18)
    elif question_relevance < 0.35:
        combined = min(combined, 0.32)

    if concept_match < 0.12:
        combined = min(combined, 0.22)
    elif concept_match < 0.25:
        combined = min(combined, 0.35)

    if question_relevance < 0.35 and concept_match < 0.25:
        combined = min(combined, 0.18)

    return _clamp(combined)


def evaluate_answer(*args, **kwargs):
    """
    Run the answer evaluation pipeline and return JSON-compatible values.
    Accepts either (reference_answer, student_answer) or the older
    (subject, reference_answer, student_answer) positional form.
    """
    subject = kwargs.get("subject")

    if args:
        if len(args) == 2:
            reference_answer, student_answer = args
        elif len(args) == 3:
            subject, reference_answer, student_answer = args
        else:
            raise TypeError("evaluate_answer expects 2 or 3 positional arguments")
    else:
        reference_answer = kwargs.get("reference_answer")
        student_answer = kwargs.get("student_answer")

    if not reference_answer or not student_answer:
        return {
            "similarity": 0.0,
            "coverage": 0.0,
            "question_relevance": 0.0,
            "score": 0,
        }

    reference_clean = preprocess_text(reference_answer)
    student_clean = preprocess_text(student_answer)
    semantic_similarity = _clamp(calculate_similarity(reference_clean, student_clean))
    concept_match, overlap = calculate_concept_match(reference_answer, student_answer)
    similarity = combine_similarity_metrics(semantic_similarity, concept_match)
    question_relevance = calculate_question_relevance(subject, student_answer)
    combined_score = combine_evaluation_score(similarity, concept_match, question_relevance)

    return {
        "similarity": round(similarity, 3),
        "semantic_similarity": round(semantic_similarity, 3),
        "coverage": round(concept_match, 3),
        "concept_match": round(concept_match, 3),
        "concept_recall": round(overlap["recall"], 3),
        "concept_precision": round(overlap["precision"], 3),
        "question_relevance": round(question_relevance, 3),
        "is_relevant": question_relevance >= 0.35,
        "score": generate_score(combined_score),
        "matched_concepts": sorted(overlap["shared_tokens"]),
        "missing_reference_concepts": sorted(overlap["source_tokens"] - overlap["shared_tokens"]),
        "extra_student_concepts": sorted(overlap["target_tokens"] - overlap["shared_tokens"]),
        "reference_answer": reference_answer,
        "student_answer": student_answer,
    }

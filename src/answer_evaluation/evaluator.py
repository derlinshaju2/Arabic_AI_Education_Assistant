from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.scoring import generate_score
from src.answer_evaluation.similarity import calculate_similarity


QUESTION_STOPWORDS = {
    "a", "an", "and", "are", "as", "be", "briefly", "define", "describe",
    "did", "do", "does", "explain", "for", "from", "give", "how", "identify",
    "in", "into", "is", "list", "mention", "of", "on", "or", "the", "to",
    "was", "were", "what", "when", "where", "which", "who", "why", "with",
}

GENERIC_QUESTIONS = {"", "general", "question", "topic", "arabic", "science", "history", "math"}


def _clamp(value):
    return max(0.0, min(1.0, float(value or 0.0)))


def _content_tokens(text):
    return {
        token
        for token in (text or "").lower().split()
        if len(token) > 2 and token not in QUESTION_STOPWORDS
    }


def _keyword_overlap(source_text, target_text):
    source_tokens = _content_tokens(source_text)
    target_tokens = _content_tokens(target_text)

    if not source_tokens or not target_tokens:
        return 0.0

    return len(source_tokens & target_tokens) / len(source_tokens)


def _question_is_generic(question):
    return (question or "").strip().lower() in GENERIC_QUESTIONS


def calculate_question_relevance(question, student_answer):
    if _question_is_generic(question):
        return 1.0

    question_clean = preprocess_text(question)
    student_clean = preprocess_text(student_answer)

    if not question_clean or not student_clean:
        return 0.0

    semantic_relevance = _clamp(calculate_similarity(question_clean, student_clean))
    keyword_relevance = _keyword_overlap(question_clean, student_clean)
    return _clamp((semantic_relevance * 0.7) + (keyword_relevance * 0.3))


def combine_evaluation_score(answer_similarity, question_relevance):
    combined = (answer_similarity * 0.75) + (question_relevance * 0.25)

    if question_relevance < 0.2:
        combined = min(combined, 0.2)
    elif question_relevance < 0.35:
        combined = min(combined, 0.4)

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
    similarity = calculate_similarity(reference_clean, student_clean)
    similarity = _clamp(similarity)
    question_relevance = calculate_question_relevance(subject, student_answer)
    combined_score = combine_evaluation_score(similarity, question_relevance)

    return {
        "similarity": round(similarity, 3),
        "coverage": round(similarity, 3),
        "question_relevance": round(question_relevance, 3),
        "is_relevant": question_relevance >= 0.35,
        "score": generate_score(combined_score),
        "reference_answer": reference_answer,
        "student_answer": student_answer,
    }

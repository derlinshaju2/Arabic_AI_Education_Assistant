from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.scoring import generate_score
from src.answer_evaluation.similarity import calculate_similarity


EVALUATION_GUIDELINES = (
    "Evaluate the student's answer based on meaning, correctness, and completeness. "
    "Focus on semantic similarity rather than exact wording. Give a score (0-10) "
    "and similarity percentage. Accept both short and long correct answers."
)

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
MAX_FEEDBACK_CONCEPTS = 5


def _clamp(value):
    return max(0.0, min(1.0, float(value or 0.0)))


def _is_arabic_text(text):
    return any("\u0600" <= char <= "\u06ff" for char in str(text or ""))


def _feedback_language(language, *texts):
    language = (language or "").strip().lower()
    if language.startswith("ar"):
        return "ar"
    if language.startswith("en"):
        return "en"
    return "ar" if any(_is_arabic_text(text) for text in texts) else "en"


def _format_concept(token):
    return str(token or "").replace("_", " ").strip()


def _limited_concepts(concepts):
    return [_format_concept(token) for token in sorted(concepts)[:MAX_FEEDBACK_CONCEPTS]]


def _more_count(concepts):
    return max(0, len(concepts) - MAX_FEEDBACK_CONCEPTS)


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
    concept_match = _clamp((overlap["recall"] * 0.85) + (overlap["precision"] * 0.15))
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
    concept_match = _clamp(concept_match)

    if adjusted_semantic >= 0.82:
        return _clamp((adjusted_semantic * 0.85) + (concept_match * 0.15))

    if concept_match < 0.12:
        adjusted_semantic *= 0.35
    elif concept_match < 0.25:
        adjusted_semantic *= 0.75
    elif concept_match < 0.4:
        adjusted_semantic *= 0.9

    combined = (adjusted_semantic * 0.75) + (concept_match * 0.25)
    return _clamp(combined)


def combine_evaluation_score(answer_similarity, concept_match, question_relevance):
    combined = (
        (answer_similarity * 0.8) +
        (concept_match * 0.1) +
        (question_relevance * 0.1)
    )

    if question_relevance < 0.2 and answer_similarity < 0.5:
        combined = min(combined, 0.18)
    elif question_relevance < 0.35 and answer_similarity < 0.6:
        combined = min(combined, 0.32)

    if concept_match < 0.12 and answer_similarity < 0.65:
        combined = min(combined, 0.22)
    elif concept_match < 0.25 and answer_similarity < 0.7:
        combined = min(combined, 0.35)

    if question_relevance < 0.35 and concept_match < 0.25 and answer_similarity < 0.6:
        combined = min(combined, 0.18)

    return _clamp(combined)


def build_feedback(result, language="en"):
    lang = _feedback_language(
        language,
        result.get("reference_answer", ""),
        result.get("student_answer", ""),
    )
    matched = result.get("matched_concepts") or []
    missing = result.get("missing_reference_concepts") or []
    relevance = _clamp(result.get("question_relevance", 1.0))

    matched_items = _limited_concepts(matched)
    missing_items = _limited_concepts(missing)
    matched_more = _more_count(matched)
    missing_more = _more_count(missing)

    if lang == "ar":
        strengths = [
            "\u0645\u0641\u0647\u0648\u0645 \u0645\u0637\u0627\u0628\u0642: {0}".format(item)
            for item in matched_items
        ]
        if matched_more:
            strengths.append(
                "\u062a\u0645\u062a \u0645\u0637\u0627\u0628\u0642\u0629 {0} \u0645\u0641\u0627\u0647\u064a\u0645 \u0623\u062e\u0631\u0649 \u0645\u0646 \u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0627\u0644\u0645\u0631\u062c\u0639\u064a\u0629.".format(matched_more)
            )
        if not strengths:
            strengths.append(
                "\u0644\u0645 \u062a\u0638\u0647\u0631 \u0645\u0641\u0627\u0647\u064a\u0645 \u0645\u0637\u0627\u0628\u0642\u0629 \u0648\u0627\u0636\u062d\u0629 \u0645\u0646 \u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0627\u0644\u0645\u0631\u062c\u0639\u064a\u0629."
            )

        areas = [
            "\u0623\u0636\u0641 \u0627\u0644\u0645\u0641\u0647\u0648\u0645 \u0627\u0644\u0646\u0627\u0642\u0635: {0}".format(item)
            for item in missing_items
        ]
        if missing_more:
            areas.append(
                "\u062a\u0648\u062c\u062f {0} \u0645\u0641\u0627\u0647\u064a\u0645 \u0645\u0631\u062c\u0639\u064a\u0629 \u0623\u062e\u0631\u0649 \u062a\u062d\u062a\u0627\u062c \u0625\u0644\u0649 \u062a\u063a\u0637\u064a\u0629.".format(missing_more)
            )
        if not areas:
            areas.append(
                "\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u0641\u0627\u0647\u064a\u0645 \u0645\u0631\u062c\u0639\u064a\u0629 \u0631\u0626\u064a\u0633\u064a\u0629 \u0645\u0641\u0642\u0648\u062f\u0629."
            )
        if relevance < 0.35:
            areas.insert(
                0,
                "\u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0644\u0627 \u062a\u0631\u062a\u0628\u0637 \u0628\u0627\u0644\u0633\u0624\u0627\u0644 \u0628\u0634\u0643\u0644 \u0648\u0627\u0636\u062d.",
            )
        elif relevance < 0.6:
            areas.insert(
                0,
                "\u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0645\u0631\u062a\u0628\u0637\u0629 \u062c\u0632\u0626\u064a\u0627 \u0628\u0627\u0644\u0633\u0624\u0627\u0644.",
            )

        if missing_items:
            steps = [
                "\u0623\u0639\u062f \u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0628\u0625\u0636\u0627\u0641\u0629: {0}.".format(
                    ", ".join(missing_items[:3])
                )
            ]
        else:
            steps = [
                "\u0631\u0627\u062c\u0639 \u0627\u0644\u0635\u064a\u0627\u063a\u0629 \u0648\u0623\u0636\u0641 \u062a\u0641\u0635\u064a\u0644\u0627 \u0648\u0627\u062d\u062f\u0627 \u062f\u0627\u0639\u0645\u0627 \u0625\u0630\u0627 \u0644\u0632\u0645."
            ]
        if relevance < 0.6:
            steps.insert(
                0,
                "\u0627\u0631\u0628\u0637 \u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0628\u0627\u0644\u0633\u0624\u0627\u0644 \u0628\u0634\u0643\u0644 \u0623\u0648\u0636\u062d.",
            )
        return {
            "language": "ar",
            "correct_concepts": strengths,
            "missing_concepts": areas,
            "suggestions": steps,
        }

    strengths = ["Matched concept: {0}".format(item) for item in matched_items]
    if matched_more:
        strengths.append("{0} additional reference concepts were matched.".format(matched_more))
    if not strengths:
        strengths.append("No clear reference concepts were matched.")

    areas = ["Add missing concept: {0}".format(item) for item in missing_items]
    if missing_more:
        areas.append("{0} additional reference concepts still need coverage.".format(missing_more))
    if not areas:
        areas.append("No major reference concepts are missing.")
    if relevance < 0.35:
        areas.insert(0, "The answer does not clearly address the question.")
    elif relevance < 0.6:
        areas.insert(0, "The answer is only partly connected to the question.")

    if missing_items:
        steps = ["Revise the answer to include: {0}.".format(", ".join(missing_items[:3]))]
    else:
        steps = ["Keep the core answer and add one precise supporting detail if needed."]
    if relevance < 0.6:
        steps.insert(0, "Tie the answer more directly to the question prompt.")

    return {
        "language": "en",
        "correct_concepts": strengths,
        "missing_concepts": areas,
        "suggestions": steps,
    }


def evaluate_answer(*args, **kwargs):
    """
    Run the answer evaluation pipeline and return JSON-compatible values.
    Accepts either (reference_answer, student_answer) or the older
    (subject, reference_answer, student_answer) positional form.
    """
    subject = kwargs.get("subject")
    language = kwargs.get("language")

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
        language = kwargs.get("language")

    if not reference_answer or not student_answer:
        empty_result = {
            "similarity": 0.0,
            "semantic_similarity": 0.0,
            "coverage": 0.0,
            "concept_match": 0.0,
            "concept_recall": 0.0,
            "concept_precision": 0.0,
            "question_relevance": 0.0,
            "is_relevant": False,
            "score": 0,
            "matched_concepts": [],
            "missing_reference_concepts": [],
            "extra_student_concepts": [],
            "reference_answer": reference_answer or "",
            "student_answer": student_answer or "",
        }
        empty_result["feedback"] = build_feedback(empty_result, language)
        return {
            **empty_result,
        }

    reference_clean = preprocess_text(reference_answer)
    student_clean = preprocess_text(student_answer)
    semantic_similarity = _clamp(calculate_similarity(reference_clean, student_clean))
    concept_match, overlap = calculate_concept_match(reference_answer, student_answer)
    similarity = combine_similarity_metrics(semantic_similarity, concept_match)
    question_relevance = calculate_question_relevance(subject, student_answer)
    threshold_similarity = combine_evaluation_score(similarity, concept_match, question_relevance)

    result = {
        "similarity": round(threshold_similarity, 3),
        "semantic_similarity": round(semantic_similarity, 3),
        "answer_similarity": round(similarity, 3),
        "coverage": round(concept_match, 3),
        "concept_match": round(concept_match, 3),
        "concept_recall": round(overlap["recall"], 3),
        "concept_precision": round(overlap["precision"], 3),
        "question_relevance": round(question_relevance, 3),
        "is_relevant": question_relevance >= 0.35,
        "score": generate_score(threshold_similarity),
        "matched_concepts": sorted(overlap["shared_tokens"]),
        "missing_reference_concepts": sorted(overlap["source_tokens"] - overlap["shared_tokens"]),
        "extra_student_concepts": sorted(overlap["target_tokens"] - overlap["shared_tokens"]),
        "reference_answer": reference_answer,
        "student_answer": student_answer,
    }
    result["feedback"] = build_feedback(result, language)
    return result

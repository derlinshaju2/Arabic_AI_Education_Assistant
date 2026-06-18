from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.similarity import calculate_similarity
from src.answer_evaluation.scoring import generate_score


def evaluate_answer(*args, **kwargs):
    """
    Full evaluation pipeline
    Returns CLEAN JSON-compatible output
    """

    if args:
        if len(args) == 2:
            reference_answer, student_answer = args
        elif len(args) == 3:
            _, reference_answer, student_answer = args
        else:
            raise TypeError("evaluate_answer expects 2 or 3 positional arguments")
    else:
        reference_answer = kwargs.get("reference_answer")
        student_answer = kwargs.get("student_answer")

    if not reference_answer or not student_answer:
        return {
            "similarity": 0.0,
            "score": 0
        }

    # Preprocess
    reference_clean = preprocess_text(reference_answer)
    student_clean = preprocess_text(student_answer)

    # Similarity
    similarity = calculate_similarity(reference_clean, student_clean)

    similarity = max(0.0, min(1.0, float(similarity)))

    # Score
    score = generate_score(similarity)

    return {
        "similarity": round(similarity, 3),
        "score": score
    }

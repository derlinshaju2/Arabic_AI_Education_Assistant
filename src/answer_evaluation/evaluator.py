from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.scoring import generate_score
from src.answer_evaluation.similarity import calculate_similarity


def evaluate_answer(*args, **kwargs):
    """
    Run the answer evaluation pipeline and return JSON-compatible values.
    Accepts either (reference_answer, student_answer) or the older
    (subject, reference_answer, student_answer) positional form.
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
            "coverage": 0.0,
            "score": 0,
        }

    reference_clean = preprocess_text(reference_answer)
    student_clean = preprocess_text(student_answer)
    similarity = calculate_similarity(reference_clean, student_clean)
    similarity = max(0.0, min(1.0, float(similarity)))

    return {
        "similarity": round(similarity, 3),
        "coverage": round(similarity, 3),
        "score": generate_score(similarity),
        "reference_answer": reference_answer,
        "student_answer": student_answer,
    }

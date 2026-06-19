from difflib import SequenceMatcher


_model = None
_model_load_failed = False


def _load_model():
    global _model, _model_load_failed

    if _model or _model_load_failed:
        return _model

    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception:
        _model_load_failed = True
        _model = None

    return _model


def _fallback_similarity(reference_answer, student_answer):
    reference_tokens = set(reference_answer.lower().split())
    student_tokens = set(student_answer.lower().split())

    if not reference_tokens or not student_tokens:
        return 0.0

    overlap = len(reference_tokens & student_tokens) / len(reference_tokens | student_tokens)
    sequence = SequenceMatcher(None, reference_answer.lower(), student_answer.lower()).ratio()
    return (overlap * 0.65) + (sequence * 0.35)


def calculate_similarity(reference_answer, student_answer):
    if not reference_answer or not student_answer:
        return 0.0

    model = _load_model()
    if not model:
        return float(_fallback_similarity(reference_answer, student_answer))

    ref_vec = model.encode([reference_answer], convert_to_tensor=True)
    stu_vec = model.encode([student_answer], convert_to_tensor=True)

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        similarity = cosine_similarity(
            ref_vec.cpu().numpy(),
            stu_vec.cpu().numpy()
        )[0][0]
        return float(similarity)
    except Exception:
        return float(_fallback_similarity(reference_answer, student_answer))

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load model ONCE (important fix)
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def calculate_similarity(reference_answer, student_answer):
    """
    Returns cosine similarity between two Arabic texts
    """

    if not reference_answer or not student_answer:
        return 0.0

    ref_vec = model.encode([reference_answer], convert_to_tensor=True)
    stu_vec = model.encode([student_answer], convert_to_tensor=True)

    similarity = cosine_similarity(
        ref_vec.cpu().numpy(),
        stu_vec.cpu().numpy()
    )[0][0]

    return float(similarity)
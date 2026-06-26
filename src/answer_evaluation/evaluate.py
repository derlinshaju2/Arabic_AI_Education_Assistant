from src.answer_evaluation.similarity import (
    calculate_similarity
)

from src.answer_evaluation.scoring import (
    generate_score
)


def evaluate_answer(reference_answer, student_answer):

    # Calculate similarity
    similarity = calculate_similarity(
        reference_answer,
        student_answer
    )

    # Generate marks
    score = generate_score(similarity)

    return similarity, score


# TEST
if __name__ == "__main__":

    reference_answer = (
        "الذكاء الاصطناعي هو فرع من علوم الحاسوب"
    )

    student_answer = (
        "الذكاء الاصطناعي مجال من مجالات الحاسوب"
    )

    similarity, score = evaluate_answer(
        reference_answer,
        student_answer
    )

    print("Similarity Score:")
    print(similarity)

    print("\nFinal Marks:")
    print(score, "/10")
import unittest
from unittest.mock import patch

from src.answer_evaluation.evaluator import evaluate_answer
from src.answer_evaluation.preprocess import preprocess_text


class ArabicPreprocessTests(unittest.TestCase):
    def test_normalizes_punctuation_and_stopwords(self):
        text = "إلى الذكاء الاصطناعي، على الحاسوب؟"

        self.assertEqual(preprocess_text(text), "الذكاء الاصطناعي الحاسوب")


class AnswerEvaluationTests(unittest.TestCase):
    def test_off_topic_answer_is_capped_even_with_semantic_similarity(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.5):
            result = evaluate_answer(
                "Define photosynthesis",
                "Photosynthesis lets plants convert light into food.",
                "The capital city has many old buildings.",
            )

        self.assertFalse(result["is_relevant"])
        self.assertLessEqual(result["score"], 2)


if __name__ == "__main__":
    unittest.main()

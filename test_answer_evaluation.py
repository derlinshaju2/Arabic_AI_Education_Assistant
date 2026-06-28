import unittest
from unittest.mock import patch

from src.answer_evaluation.evaluator import evaluate_answer
from src.answer_evaluation.preprocess import preprocess_text
from src.answer_evaluation.scoring import generate_score


class ArabicPreprocessTests(unittest.TestCase):
    def test_normalizes_punctuation_and_stopwords(self):
        text = (
            "\u0625\u0644\u0649 \u0627\u0644\u0630\u0643\u0627\u0621 "
            "\u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a\u060c "
            "\u0639\u0644\u0649 \u0627\u0644\u062d\u0627\u0633\u0648\u0628\u061f"
        )

        self.assertEqual(
            preprocess_text(text),
            "\u0627\u0644\u0630\u0643\u0627\u0621 "
            "\u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a "
            "\u0627\u0644\u062d\u0627\u0633\u0648\u0628",
        )


class AnswerEvaluationTests(unittest.TestCase):
    def test_short_correct_answer_gets_semantic_credit(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.88):
            result = evaluate_answer(
                "General",
                "Photosynthesis is the process by which plants use sunlight, carbon dioxide, and water to produce glucose and oxygen.",
                "Plants use sunlight to make food.",
            )

        self.assertGreaterEqual(result["similarity"], 0.75)
        self.assertGreaterEqual(result["score"], 7)

    def test_long_correct_answer_accepts_extra_detail(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.92):
            result = evaluate_answer(
                "General",
                "Photosynthesis is the process by which plants use sunlight, carbon dioxide, and water to produce glucose and oxygen.",
                "Photosynthesis happens in plants when they capture sunlight and use carbon dioxide and water to make glucose, which stores energy, and oxygen is released.",
            )

        self.assertGreaterEqual(result["similarity"], 0.85)
        self.assertGreaterEqual(result["score"], 8)

    def test_off_topic_answer_is_capped_even_with_semantic_similarity(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.5):
            result = evaluate_answer(
                "Define photosynthesis",
                "Photosynthesis lets plants convert light into food.",
                "The capital city has many old buildings.",
            )

        self.assertFalse(result["is_relevant"])
        self.assertLessEqual(result["score"], 2)

    def test_score_follows_displayed_similarity_threshold(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.78):
            result = evaluate_answer(
                "General",
                "Plants need sunlight and water to produce glucose and oxygen.",
                "Plants use sunlight and water to make glucose.",
            )

        self.assertEqual(result["score"], generate_score(result["similarity"]))

    def test_feedback_uses_actual_concepts_and_language(self):
        with patch("src.answer_evaluation.evaluator.calculate_similarity", return_value=0.82):
            result = evaluate_answer(
                "General",
                "Photosynthesis uses sunlight water carbon dioxide glucose oxygen",
                "Photosynthesis uses sunlight and water",
                language="ar",
            )

        feedback = result["feedback"]
        self.assertEqual(feedback["language"], "ar")
        self.assertIn("sunlight", " ".join(feedback["correct_concepts"]))
        self.assertIn("glucose", " ".join(feedback["missing_concepts"]))
        self.assertNotIn("Core concepts understood", " ".join(feedback["correct_concepts"]))


if __name__ == "__main__":
    unittest.main()

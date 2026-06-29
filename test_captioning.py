import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_captioning import pipeline
from src.image_captioning import translator


class CaptionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.similarity_patcher = patch(
            "src.image_captioning.pipeline._image_text_similarity",
            return_value={},
        )
        self.visual_patcher = patch(
            "src.image_captioning.pipeline._visual_evidence",
            return_value={
                "detected_counts": {},
                "classifier_object": "",
                "verified_objects": set(),
            },
        )
        self.similarity_patcher.start()
        self.visual_patcher.start()

    def tearDown(self):
        self.visual_patcher.stop()
        self.similarity_patcher.stop()

    def test_prompt_echo_uses_fallback_caption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            with patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                return_value="a clear and realistic description of the image",
            ), patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._classifier_caption",
                return_value="a photo of a dog",
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "A dog is visible.")

    def test_prefers_main_subject_before_background_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            def fake_generate(_image, _options, prompt=None):
                if prompt and "dog" in prompt:
                    return "a dog playing in the grass"
                return "a grassy field with trees and a dog in the background"

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                side_effect=fake_generate,
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "A dog is playing in the grass.")

    def test_classifier_label_becomes_readable_caption(self):
        self.assertEqual(
            pipeline._caption_from_label("tabby, tabby cat"),
            "a tabby is visible",
        )

    def test_low_confidence_classifier_label_is_ignored(self):
        self.assertEqual(
            pipeline._label_from_classifier_scores(
                [0.12, 0.18],
                {0: "dog", 1: "cat"},
                min_confidence=0.20,
            ),
            "",
        )

    def test_high_confidence_classifier_label_is_used(self):
        self.assertEqual(
            pipeline._label_from_classifier_scores(
                [0.12, 0.88],
                {0: "dog", 1: "tabby, tabby cat"},
                min_confidence=0.20,
            ),
            "tabby",
        )

    def test_speculative_relationship_claims_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                return_value="a happy dog seems to be playing with his owner",
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "A dog is playing with a person.")

    def test_unsupported_scene_label_is_removed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            def fake_generate(_image, _options, prompt=None):
                if prompt and "dog" in prompt:
                    return "a dog sitting in a restaurant"
                return "a dog sitting on grass"

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                side_effect=fake_generate,
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "A dog is sitting on grass.")

    def test_vague_people_quantity_becomes_visible_people(self):
        self.assertEqual(
            pipeline._finalize_caption("a group of people standing near a car"),
            "People are standing near a car.",
        )

    def test_caption_finalizer_returns_one_sentence(self):
        self.assertEqual(
            pipeline._finalize_caption("a dog sitting on grass. a restaurant is nearby"),
            "A dog is sitting on grass.",
        )

    def test_caption_finalizer_removes_image_filler(self):
        self.assertEqual(
            pipeline._finalize_caption("a dog sitting in the image"),
            "A dog is sitting.",
        )

    def test_caption_finalizer_removes_close_up_filler(self):
        self.assertEqual(
            pipeline._finalize_caption("a close-up of a dog", primary_label="dog"),
            "A dog is visible.",
        )

    def test_caption_finalizer_removes_generic_photo_prefix(self):
        self.assertEqual(
            pipeline._finalize_caption("a photo of a dog sitting on grass"),
            "A dog is sitting on grass.",
        )

    def test_similarity_ranking_selects_best_visible_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            def fake_generate(_image, _options, prompt=None):
                if prompt and "dog" in prompt:
                    return "a dog sitting indoors"
                return "a cart standing on a street"

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                side_effect=fake_generate,
            ), patch(
                "src.image_captioning.pipeline._image_text_similarity",
                return_value={
                    "a dog is sitting": 0.2,
                    "a cart is standing on a street": 0.9,
                },
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "A cart is standing on a street.")

    def test_caption_result_tracks_each_uploaded_image_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = Path(tmpdir) / "first.jpg"
            second_path = Path(tmpdir) / "second.jpg"
            Image.new("RGB", (24, 24), color="white").save(first_path)
            Image.new("RGB", (24, 24), color="black").save(second_path)

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                return_value="a dog sitting on grass",
            ):
                first = pipeline.generate_caption_result(first_path)
                second = pipeline.generate_caption_result(second_path)

        self.assertNotEqual(first["image_hash"], second["image_hash"])
        self.assertEqual(first["selected_english_caption"], "A dog is sitting on grass.")
        self.assertEqual(second["selected_english_caption"], "A dog is sitting on grass.")
        self.assertIn("a dog sitting on grass", first["generated_candidates"])

    def test_visual_count_verification_rejects_single_animal_when_two_are_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            def fake_generate(_image, _options, prompt=None):
                if prompt and "dog" in prompt:
                    return "a dog sitting on grass"
                return "two dogs sitting on grass"

            with patch(
                "src.image_captioning.pipeline._classifier_label",
                return_value="dog",
            ), patch(
                "src.image_captioning.pipeline._visual_evidence",
                return_value={
                    "detected_counts": {"dog": 2},
                    "classifier_object": "dog",
                    "verified_objects": {"dog"},
                },
            ), patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                side_effect=fake_generate,
            ):
                result = pipeline.generate_caption_result(image_path)

        self.assertEqual(result["selected_english_caption"], "Two dogs are sitting on grass.")
        self.assertTrue(
            any(
                diagnostic["reason"] == "count_mismatch:dog:1_vs_2"
                for diagnostic in result["candidate_diagnostics"]
            )
        )

    def test_visual_object_verification_rejects_net_as_satellite_dish(self):
        evidence = {
            "candidate_objects": {"net": 2, "satellite dish": 1},
            "candidate_count_claims": {},
        }
        visual = {
            "detected_counts": {"net": 1},
            "classifier_object": "net",
            "verified_objects": {"net"},
        }

        self.assertEqual(
            pipeline._invalid_caption_reason("a satellite dish is beside a wall", evidence, visual),
            "unsupported_object:satellite dish",
        )
        self.assertEqual(
            pipeline._invalid_caption_reason("a net is beside a wall", evidence, visual),
            "",
        )

    def test_template_arabic_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A dog is playing in the grass."),
            "كلب يلعب على العشب.",
        )

    def test_template_arabic_caption_matches_plural_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("People are standing near a car."),
            "أشخاص واقفون بالقرب من سيارة.",
        )

    def test_template_arabic_caption_translates_simple_visible_place(self):
        self.assertEqual(
            translator.translate_to_arabic("A black dog is sitting on a couch."),
            "كلب أسود جالس على أريكة.",
        )

    def test_template_arabic_caption_matches_fallback_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("Visible objects are present."),
            "\u062a\u0648\u062c\u062f \u0623\u0634\u064a\u0627\u0621 \u0645\u0631\u0626\u064a\u0629.",
        )

    def test_template_arabic_photo_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A photo of a dog."),
            "صورة لكلب.",
        )

    def test_template_arabic_visible_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A dog is visible."),
            f"\u064a\u0638\u0647\u0631 {translator.NOUNS['dog']}.",
        )


if __name__ == "__main__":
    unittest.main()

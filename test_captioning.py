import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_captioning import pipeline
from src.image_captioning import translator


class CaptionPipelineTests(unittest.TestCase):
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

        self.assertEqual(caption, "A photo of a dog.")

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
            "a photo of a tabby",
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
            "A photo of a dog.",
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
            translator.translate_to_arabic("A photo with visible objects."),
            "صورة تحتوي على أشياء مرئية.",
        )

    def test_template_arabic_photo_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A photo of a dog."),
            "صورة لكلب.",
        )


if __name__ == "__main__":
    unittest.main()

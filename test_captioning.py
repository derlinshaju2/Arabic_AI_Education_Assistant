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

        self.assertEqual(caption, "A dog playing in the grass.")

    def test_classifier_label_becomes_readable_caption(self):
        self.assertEqual(
            pipeline._caption_from_label("tabby, tabby cat"),
            "a photo of a tabby",
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

        self.assertEqual(caption, "A dog playing with a person.")

    def test_template_arabic_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A dog playing in the grass."),
            "كلب يلعب على العشب.",
        )

    def test_template_arabic_photo_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A photo of a dog."),
            "صورة لكلب.",
        )


if __name__ == "__main__":
    unittest.main()

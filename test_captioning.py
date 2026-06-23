import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_captioning import pipeline


class CaptionPipelineTests(unittest.TestCase):
    def test_prompt_echo_uses_fallback_caption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)

            with patch(
                "src.image_captioning.pipeline._generate_blip_caption",
                return_value="a clear and realistic description of the image",
            ), patch(
                "src.image_captioning.pipeline._classifier_caption",
                return_value="a photo of a dog",
            ):
                caption = pipeline.generate_caption(image_path)

        self.assertEqual(caption, "a photo of a dog")

    def test_classifier_label_becomes_readable_caption(self):
        self.assertEqual(
            pipeline._caption_from_label("tabby, tabby cat"),
            "a photo of a tabby",
        )


if __name__ == "__main__":
    unittest.main()

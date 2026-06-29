import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_captioning import pipeline
from src.image_captioning import translator


def image_bytes(image_format):
    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), color="white").save(buffer, format=image_format)
    buffer.seek(0)
    return buffer


class CaptionPipelineTests(unittest.TestCase):
    def assert_translation(self, english, expected_arabic):
        self.assertEqual(translator.translate_to_arabic(english), expected_arabic)

    def test_prompt_echo_is_rejected(self):
        raw_candidates = [
            {"caption": "a clear and realistic description of the image", "model_score": 0.0},
            {"caption": "a dog sitting on grass", "model_score": 0.2},
        ]

        selected, diagnostics, _evidence = pipeline._select_best_caption(raw_candidates)

        self.assertEqual(selected["caption"], "a dog is sitting on grass")
        self.assertTrue(any(item["reason"] == "generic" for item in diagnostics))

    def test_blip_generation_uses_raw_image_without_text_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            Image.new("RGB", (24, 24), color="white").save(image_path)
            calls = []

            def fake_generate(_image, options):
                calls.append(options)
                return [("a dog on grass", 0.2)]

            with patch("src.image_captioning.pipeline._generate_blip_candidates", side_effect=fake_generate):
                result = pipeline.generate_caption_result(image_path)

        self.assertEqual(result["selected_english_caption"], "A dog is on grass.")
        self.assertEqual(len(calls), 2)

    def test_prefers_supported_main_subject_before_background_details(self):
        raw_candidates = [
            {"caption": "a grassy field with trees and a dog in the background", "model_score": 0.1},
            {"caption": "a dog playing in the grass", "model_score": 0.2},
        ]

        selected, _diagnostics, _evidence = pipeline._select_best_caption(raw_candidates)

        self.assertEqual(pipeline._finalize_caption(selected["caption"]), "A dog is playing in the grass.")

    def test_one_dog_caption_preserves_single_subject_in_arabic(self):
        english = pipeline._finalize_caption("a dog on grass")

        self.assertEqual(english, "A dog is on grass.")
        self.assert_translation(
            english,
            f"{translator.NOUNS['dog']} \u0639\u0644\u0649 \u0627\u0644\u0639\u0634\u0628.",
        )

    def test_two_dogs_caption_preserves_dual_subject_in_arabic(self):
        english = pipeline._finalize_caption("two dog sitting on grass")

        self.assertEqual(english, "Two dogs are sitting on grass.")
        self.assert_translation(
            english,
            "\u0643\u0644\u0628\u0627\u0646 \u062c\u0627\u0644\u0633\u0627\u0646 \u0639\u0644\u0649 \u0627\u0644\u0639\u0634\u0628.",
        )

    def test_people_caption_preserves_plural_subject_in_arabic(self):
        english = pipeline._finalize_caption("people standing near a car")

        self.assertEqual(english, "People are standing near a car.")
        self.assert_translation(
            english,
            f"{translator.NOUNS['people']} {translator.PLURAL_ACTIONS['standing']}{translator._translate_rest('near a car')}.",
        )

    def test_object_caption_preserves_object_and_scene_in_arabic(self):
        english = pipeline._finalize_caption("a cart on a street")

        self.assertEqual(english, "A cart is on a street.")
        self.assert_translation(
            english,
            f"{translator.NOUNS['cart']}{translator._translate_rest('on a street')}.",
        )

    def test_scene_caption_preserves_location_in_arabic(self):
        english = pipeline._finalize_caption("a dog in a room")

        self.assertEqual(english, "A dog is in a room.")
        self.assert_translation(
            english,
            f"{translator.NOUNS['dog']}{translator._translate_rest('in a room')}.",
        )

    def test_cleanup_preserves_detected_relationship_words(self):
        self.assertEqual(
            pipeline._finalize_caption("a happy dog seems to be playing with his owner"),
            "A happy dog seems to be playing with his owner.",
        )

    def test_cleanup_does_not_replace_detected_people_description(self):
        self.assertEqual(
            pipeline._finalize_caption("a group of people standing near a car"),
            "A group of people is standing near a car.",
        )

    def test_cleanup_does_not_invent_details(self):
        caption = pipeline._finalize_caption("a dog sitting")

        self.assertEqual(caption, "A dog is sitting.")
        for invented_detail in ("poodle", "park", "two dogs", "running"):
            self.assertNotIn(invented_detail, caption.lower())

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

    def test_caption_finalizer_removes_generic_photo_prefix(self):
        self.assertEqual(
            pipeline._finalize_caption("a photo of a dog sitting on grass"),
            "A dog is sitting on grass.",
        )

    def test_count_consensus_rejects_single_animal_when_two_are_supported(self):
        raw_candidates = [
            {"caption": "a dog sitting on grass", "model_score": 0.4},
            {"caption": "two dogs sitting on grass", "model_score": 0.3},
            {"caption": "two dogs sitting on grass near a road", "model_score": 0.2},
        ]

        selected, diagnostics, _evidence = pipeline._select_best_caption(raw_candidates)

        self.assertEqual(pipeline._finalize_caption(selected["caption"]), "Two dogs are sitting on grass near a road.")
        self.assertTrue(
            any(
                diagnostic["reason"] == "count_conflict:dog:1_vs_2"
                for diagnostic in diagnostics
            )
        )

    def test_caption_result_tracks_each_uploaded_image_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = Path(tmpdir) / "first.jpg"
            second_path = Path(tmpdir) / "second.png"
            Image.new("RGB", (24, 24), color="white").save(first_path)
            Image.new("RGB", (24, 24), color="black").save(second_path)

            with patch(
                "src.image_captioning.pipeline._generate_blip_candidates",
                return_value=[("a dog sitting on grass", 0.2)],
            ):
                first = pipeline.generate_caption_result(first_path)
                second = pipeline.generate_caption_result(second_path)

        self.assertNotEqual(first["image_hash"], second["image_hash"])
        self.assertEqual(first["selected_english_caption"], "A dog is sitting on grass.")
        self.assertEqual(second["selected_english_caption"], "A dog is sitting on grass.")
        self.assertIn("a dog sitting on grass", first["generated_candidates"])

    def test_invalid_image_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "not-image.jpg"
            image_path.write_text("not an image", encoding="utf-8")

            with self.assertRaises(pipeline.InvalidImageError):
                pipeline.generate_caption_result(image_path)

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
            "توجد أشياء مرئية.",
        )

    def test_template_arabic_photo_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A photo of a dog."),
            "صورة لكلب.",
        )

    def test_template_arabic_visible_caption_matches_simple_english_caption(self):
        self.assertEqual(
            translator.translate_to_arabic("A dog is visible."),
            f"يظهر {translator.NOUNS['dog']}.",
        )


class CaptionRouteTests(unittest.TestCase):
    def post_caption(self, filename, payload):
        from app import app

        app.config.update(TESTING=True)
        user = {"id": 1, "name": "Test User", "email": "test@example.com"}
        with patch("app.current_user", return_value=user), patch("app.log_activity"):
            with app.test_client() as client:
                return client.post(
                    "/caption",
                    data={"image": (payload, filename)},
                    content_type="multipart/form-data",
                )

    def test_caption_accepts_jpg_image(self):
        with patch("src.image_captioning.pipeline._generate_blip_candidates", return_value=[("a dog sitting on grass", 0.2)]):
            response = self.post_caption("sample.jpg", image_bytes("JPEG"))

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["english_caption"], "A dog is sitting on grass.")
        self.assertEqual(
            data["arabic_caption"],
            f"{translator.NOUNS['dog']} {translator.ACTIONS['sitting']}{translator._translate_rest('on grass')}.",
        )

    def test_caption_accepts_png_image(self):
        with patch("src.image_captioning.pipeline._generate_blip_candidates", return_value=[("a cart standing on a street", 0.2)]):
            response = self.post_caption("sample.png", image_bytes("PNG"))

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["english_caption"], "A cart is standing on a street.")
        self.assertEqual(
            data["arabic_caption"],
            f"{translator.NOUNS['cart']} {translator.ACTIONS['standing']}{translator._translate_rest('on a street')}.",
        )

    def test_caption_translates_cleaned_english_once(self):
        expected_arabic = "\u0643\u0644\u0628 \u062c\u0627\u0644\u0633 \u0639\u0644\u0649 \u0627\u0644\u0639\u0634\u0628."
        with patch(
            "src.image_captioning.pipeline._generate_blip_candidates",
            return_value=[("a dog sitting on grass", 0.2)],
        ), patch(
            "src.image_captioning.translator.translate_to_arabic",
            return_value=expected_arabic,
        ) as translate:
            response = self.post_caption("sample.jpg", image_bytes("JPEG"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["arabic_caption"], expected_arabic)
        translate.assert_called_once_with("A dog is sitting on grass.")

    def test_caption_returns_detailed_json_for_invalid_image(self):
        response = self.post_caption("sample.jpg", io.BytesIO(b"not an image"))

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error"], "invalid_image")


if __name__ == "__main__":
    unittest.main()

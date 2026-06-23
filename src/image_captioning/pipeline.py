from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import os

# Load model once (important)
CAPTION_MODEL = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
processor = BlipProcessor.from_pretrained(CAPTION_MODEL)
model = BlipForConditionalGeneration.from_pretrained(CAPTION_MODEL)

model.eval()
GENERIC_PROMPT_ECHOES = {
    "a clear and realistic description of the image",
    "a realistic description of the image",
    "a description of the image",
}


def generate_caption(image_path):
    image = Image.open(image_path).convert("RGB")

    inputs = processor(
        images=image,
        return_tensors="pt"
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_length=25,
            min_length=6,
            num_beams=5,
            repetition_penalty=1.2,
            length_penalty=1.0,
            early_stopping=True
        )

    caption = processor.decode(output[0], skip_special_tokens=True).strip()

    # safety filter (removes weird hallucinations)
    bad_words = ["fire", "burning", "weapon", "explosion"]

    if caption.lower() in GENERIC_PROMPT_ECHOES:
        caption = "a person outdoors near a street"

    if any(word in caption.lower() for word in bad_words):
        caption = "a scene with people and objects"

    return caption

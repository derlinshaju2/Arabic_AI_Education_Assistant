from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import os

# Load model once (important)
CAPTION_MODEL = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
processor = BlipProcessor.from_pretrained(CAPTION_MODEL)
model = BlipForConditionalGeneration.from_pretrained(CAPTION_MODEL)

model.eval()


def generate_caption(image_path):
    image = Image.open(image_path).convert("RGB")

    # guided prompt (VERY IMPORTANT for accuracy)
    inputs = processor(
        images=image,
        text="a clear and realistic description of the image",
        return_tensors="pt"
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_length=25,
            num_beams=3,
            repetition_penalty=1.5,
            early_stopping=True
        )

    caption = processor.decode(output[0], skip_special_tokens=True)

    # safety filter (removes weird hallucinations)
    bad_words = ["fire", "burning", "weapon", "explosion"]

    if any(word in caption.lower() for word in bad_words):
        caption = "a scene with people and objects"

    return caption

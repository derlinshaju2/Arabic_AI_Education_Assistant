from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch

# Load model once (important)
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-large"
)

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
            num_beams=7,
            repetition_penalty=1.5,
            early_stopping=True
        )

    caption = processor.decode(output[0], skip_special_tokens=True)

    # safety filter (removes weird hallucinations)
    bad_words = ["fire", "burning", "weapon", "explosion"]

    if any(word in caption.lower() for word in bad_words):
        caption = "a scene with people and objects"

    return caption
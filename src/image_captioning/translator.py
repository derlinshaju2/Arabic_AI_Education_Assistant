from transformers import MarianMTModel, MarianTokenizer
import torch

MODEL = "Helsinki-NLP/opus-mt-en-ar"

tokenizer = MarianTokenizer.from_pretrained(MODEL)
model = MarianMTModel.from_pretrained(MODEL)

model.eval()


def translate_to_arabic(text):
    if not text:
        return ""

    text = text.strip()

    inputs = tokenizer(
        [text],
        return_tensors="pt",
        padding=True,
        truncation=True
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_length=60,
            num_beams=5,
            early_stopping=True
        )

    return tokenizer.decode(output[0], skip_special_tokens=True)
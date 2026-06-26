from src.image_captioning.translator import (
    translate_to_arabic
)

english_caption = "a boy is playing football"

arabic_caption = translate_to_arabic(
    english_caption
)

print("English:", english_caption)
print("Arabic:", arabic_caption)
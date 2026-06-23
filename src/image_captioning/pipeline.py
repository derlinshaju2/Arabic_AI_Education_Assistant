import os
import re

from PIL import Image


CAPTION_MODEL = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
CLASSIFIER_MODEL = os.environ.get("IMAGE_CLASSIFIER_MODEL", "microsoft/resnet-50")
ENABLE_CLASSIFIER_FALLBACK = os.environ.get("IMAGE_CLASSIFIER_FALLBACK", "1").lower() not in {
    "0",
    "false",
    "no",
}

GENERIC_PROMPT_ECHOES = {
    "a clear and realistic description of the image",
    "a realistic description of the image",
    "a description of the image",
    "clear and realistic description of the image",
    "realistic description of the image",
    "description of the image",
}
GENERIC_CAPTION_FRAGMENTS = (
    "description of the image",
    "clear and realistic",
    "image shown",
    "uploaded image",
)
BACKGROUND_FIRST_TERMS = (
    "a background",
    "a field",
    "a grassy field",
    "a room",
    "a street",
    "a table",
    "a wall",
    "an outdoor",
    "the background",
    "the grass",
    "the room",
    "the street",
)
ACTION_WORDS = {
    "carrying",
    "eating",
    "flying",
    "holding",
    "jumping",
    "laying",
    "lying",
    "looking",
    "playing",
    "riding",
    "running",
    "sitting",
    "standing",
    "walking",
    "wearing",
}
SCENE_WORDS = {"at", "beside", "in", "inside", "near", "next", "on", "outside", "under", "with"}
STRONG_CAPTION_SCORE = 8.0

_torch = None
_device = None
_caption_processor = None
_caption_model = None
_classifier_processor = None
_classifier_model = None
_classifier_load_failed = False


def _normalized_caption(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _is_generic_caption(caption):
    normalized = _normalized_caption(caption).lower().strip(".")
    return (
        not normalized
        or normalized in GENERIC_PROMPT_ECHOES
        or any(fragment in normalized for fragment in GENERIC_CAPTION_FRAGMENTS)
    )


def _article_for(text):
    return "an" if (text or "")[:1].lower() in "aeiou" else "a"


def _load_torch():
    global _torch

    if _torch is None:
        import torch

        _torch = torch

    return _torch


def _get_device():
    global _device

    if _device is None:
        torch = _load_torch()
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    return _device


def _load_caption_model():
    global _caption_processor, _caption_model

    if _caption_processor is None or _caption_model is None:
        from transformers import BlipForConditionalGeneration, BlipProcessor

        device = _get_device()
        _caption_processor = BlipProcessor.from_pretrained(CAPTION_MODEL)
        _caption_model = BlipForConditionalGeneration.from_pretrained(CAPTION_MODEL).to(device)
        _caption_model.eval()

    return _caption_processor, _caption_model


def _load_classifier_model():
    global _classifier_processor, _classifier_model, _classifier_load_failed

    if not ENABLE_CLASSIFIER_FALLBACK or _classifier_load_failed:
        return None, None

    if _classifier_processor is None or _classifier_model is None:
        try:
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            device = _get_device()
            _classifier_processor = AutoImageProcessor.from_pretrained(CLASSIFIER_MODEL)
            _classifier_model = AutoModelForImageClassification.from_pretrained(CLASSIFIER_MODEL).to(device)
            _classifier_model.eval()
        except Exception:
            _classifier_load_failed = True
            return None, None

    return _classifier_processor, _classifier_model


def _move_to_device(inputs):
    device = _get_device()
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }


def _decode_caption(processor, output):
    return _normalized_caption(processor.decode(output[0], skip_special_tokens=True))


def _generate_blip_caption(image, generation_options, prompt=None):
    torch = _load_torch()
    processor, model = _load_caption_model()
    if prompt:
        inputs = processor(images=image, text=prompt, return_tensors="pt")
    else:
        inputs = processor(images=image, return_tensors="pt")
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        output = model.generate(**inputs, **generation_options)

    return _decode_caption(processor, output)


def _clean_classifier_label(label):
    label = (label or "").split(",")[0].replace("_", " ").strip().lower()
    label = re.sub(r"\b[a-z]?\d+\b", "", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label


def _caption_from_label(label):
    label = _clean_classifier_label(label)
    if not label:
        return ""

    return f"a photo of {_article_for(label)} {label}"


def _classifier_label(image):
    processor, model = _load_classifier_model()
    if processor is None or model is None:
        return ""

    torch = _load_torch()
    inputs = processor(images=image, return_tensors="pt")
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        logits = model(**inputs).logits

    predicted_id = int(logits.argmax(-1).item())
    label = model.config.id2label.get(predicted_id, "")
    return _clean_classifier_label(label)


def _classifier_caption(image):
    return _caption_from_label(_classifier_label(image))


def _caption_prompts(primary_label):
    prompts = [
        "a photo of",
        None,
    ]

    if primary_label:
        article = _article_for(primary_label)
        prompts.insert(0, f"a photo of {article} {primary_label}")

    unique_prompts = []
    for prompt in prompts:
        if prompt not in unique_prompts:
            unique_prompts.append(prompt)

    return unique_prompts


def _caption_words(caption):
    return re.findall(r"[a-zA-Z]+", (caption or "").lower())


def _caption_mentions_label(caption, primary_label):
    if not primary_label:
        return False

    caption_words = set(_caption_words(caption))
    label_words = set(_caption_words(primary_label))
    return bool(label_words and label_words <= caption_words)


def _label_position(caption, primary_label):
    if not primary_label:
        return None

    words = _caption_words(caption)
    label_words = _caption_words(primary_label)
    if not words or not label_words:
        return None

    first_label_word = label_words[0]
    try:
        return words.index(first_label_word)
    except ValueError:
        return None


def _caption_score(caption, primary_label=""):
    if _is_generic_caption(caption):
        return -100.0

    normalized = _normalized_caption(caption).lower()
    words = _caption_words(normalized)
    score = min(len(words), 18) * 0.18

    if len(words) < 5:
        score -= 2.0
    if len(words) >= 8:
        score += 1.0

    if normalized.startswith(("a photo of", "an image of", "a picture of")):
        score += 1.2

    if primary_label and _caption_mentions_label(normalized, primary_label):
        score += 3.5
        position = _label_position(normalized, primary_label)
        if position is not None and position <= 5:
            score += 2.0
        elif position is not None and position > 8:
            score -= 1.5

    if any(word in ACTION_WORDS for word in words):
        score += 1.5

    if any(word in SCENE_WORDS for word in words):
        score += 1.0

    if normalized.startswith(BACKGROUND_FIRST_TERMS):
        score -= 2.5

    return score


def _strip_prompt_lead(caption):
    caption = _normalized_caption(caption)
    caption = re.sub(
        r"^(?:the main subject(?: of the image)? is|this image shows|the image shows)\s+",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    return _normalized_caption(caption)


def _finalize_caption(caption, primary_label=""):
    caption = _strip_prompt_lead(caption)

    if _is_generic_caption(caption) or len(_caption_words(caption)) < 4:
        caption = _caption_from_label(primary_label)

    caption = _normalized_caption(caption).strip(" .")
    if not caption:
        caption = "a photo with a visible main subject and surrounding scene"

    return caption[:1].upper() + caption[1:] + "."


def _best_caption(candidates, primary_label=""):
    usable_candidates = [
        _strip_prompt_lead(candidate)
        for candidate in candidates
        if not _is_generic_caption(candidate)
    ]

    if not usable_candidates:
        return ""

    return max(
        usable_candidates,
        key=lambda candidate: _caption_score(candidate, primary_label),
    )


def generate_caption(image_path):
    with Image.open(image_path) as uploaded_image:
        image = uploaded_image.convert("RGB")

    primary_label = _classifier_label(image)
    generation_attempts = (
        {
            "max_new_tokens": 30,
            "min_length": 8,
            "num_beams": 3,
            "repetition_penalty": 1.1,
            "length_penalty": 1.0,
            "early_stopping": True,
        },
        {
            "max_new_tokens": 40,
            "min_length": 10,
            "num_beams": 5,
            "repetition_penalty": 1.2,
            "length_penalty": 0.9,
            "early_stopping": True,
        },
    )

    candidates = []
    for options in generation_attempts:
        for prompt in _caption_prompts(primary_label):
            caption = _generate_blip_caption(image, options, prompt=prompt)
            if caption and caption not in candidates:
                candidates.append(caption)

        best_caption = _best_caption(candidates, primary_label)
        if best_caption and _caption_score(best_caption, primary_label) >= STRONG_CAPTION_SCORE:
            return _finalize_caption(best_caption, primary_label)

    best_caption = _best_caption(candidates, primary_label)
    if best_caption:
        return _finalize_caption(best_caption, primary_label)

    fallback_caption = _classifier_caption(image)
    if fallback_caption:
        return _finalize_caption(fallback_caption, primary_label)

    return "A photo with a visible main subject and surrounding scene."

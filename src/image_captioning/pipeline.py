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


def _generate_blip_caption(image, generation_options):
    torch = _load_torch()
    processor, model = _load_caption_model()
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

    article = "an" if label[0] in "aeiou" else "a"
    return f"a photo of {article} {label}"


def _classifier_caption(image):
    torch = _load_torch()
    processor, model = _load_classifier_model()
    if processor is None or model is None:
        return ""

    inputs = processor(images=image, return_tensors="pt")
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        logits = model(**inputs).logits

    predicted_id = int(logits.argmax(-1).item())
    label = model.config.id2label.get(predicted_id, "")
    return _caption_from_label(label)


def generate_caption(image_path):
    with Image.open(image_path) as uploaded_image:
        image = uploaded_image.convert("RGB")

    generation_attempts = (
        {
            "max_new_tokens": 30,
            "num_beams": 3,
            "repetition_penalty": 1.1,
            "length_penalty": 1.0,
            "early_stopping": True,
        },
        {
            "max_new_tokens": 40,
            "num_beams": 5,
            "repetition_penalty": 1.2,
            "length_penalty": 0.9,
            "early_stopping": True,
        },
    )

    for options in generation_attempts:
        caption = _generate_blip_caption(image, options)
        if not _is_generic_caption(caption):
            return caption

    fallback_caption = _classifier_caption(image)
    if fallback_caption:
        return fallback_caption

    return "a photo with visible objects and background details"

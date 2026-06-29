import hashlib
import logging
import os
import re

from PIL import Image


LOGGER = logging.getLogger(__name__)


def _float_env(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _bool_env(name, default):
    return os.environ.get(name, default).lower() not in {"0", "false", "no"}


CAPTION_MODEL = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
CLASSIFIER_MODEL = os.environ.get("IMAGE_CLASSIFIER_MODEL", "microsoft/resnet-50")
SIMILARITY_MODEL = os.environ.get("IMAGE_TEXT_SIMILARITY_MODEL", "openai/clip-vit-base-patch32")
CLASSIFIER_MIN_CONFIDENCE = _float_env("IMAGE_CLASSIFIER_MIN_CONFIDENCE", "0.20")
ENABLE_CLASSIFIER_FALLBACK = _bool_env("IMAGE_CLASSIFIER_FALLBACK", "1")
ENABLE_SIMILARITY_RANKING = _bool_env("IMAGE_TEXT_SIMILARITY_RANKING", "1")

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
    "image contains",
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
SCENE_LABEL_WORDS = {
    "airport",
    "beach",
    "city",
    "classroom",
    "field",
    "forest",
    "kitchen",
    "office",
    "park",
    "restaurant",
    "room",
    "school",
    "street",
    "yard",
}
IMPORTANT_VISIBLE_WORDS = {
    "animal",
    "animals",
    "bicycle",
    "bicycles",
    "bird",
    "birds",
    "boat",
    "boats",
    "bus",
    "buses",
    "car",
    "cars",
    "cart",
    "carts",
    "cat",
    "cats",
    "cow",
    "cows",
    "dog",
    "dogs",
    "horse",
    "horses",
    "motorcycle",
    "motorcycles",
    "road",
    "street",
    "truck",
    "trucks",
    "vehicle",
    "vehicles",
}
TRAILING_PREPOSITIONS = {"at", "beside", "by", "in", "inside", "near", "of", "on", "outside", "under", "with"}
SPECULATIVE_PHRASES = (
    "appears to be",
    "appears like",
    "looks like it is",
    "looks like",
    "might be",
    "possibly",
    "probably",
    "seems to be",
    "seems like",
)
UNSUPPORTED_RELATIONSHIP_TERMS = {
    "boyfriend",
    "brother",
    "couple",
    "daughter",
    "family",
    "father",
    "friend",
    "friends",
    "girlfriend",
    "mother",
    "owner",
    "parents",
    "sister",
    "son",
}
SUBJECTIVE_MODIFIERS = {
    "adorable",
    "angry",
    "beautiful",
    "cute",
    "happy",
    "old",
    "sad",
    "scared",
    "young",
}
EVENT_GUESSES = {
    "birthday",
    "ceremony",
    "concert",
    "festival",
    "party",
    "wedding",
}
VAGUE_WORDS = {
    "bunch",
    "group",
    "many",
    "several",
    "something",
    "stuff",
    "thing",
    "things",
    "various",
}
IMAGE_QUALITY_WORDS = {
    "blurry",
    "detailed",
    "quality",
    "realistic",
}
STRONG_CAPTION_SCORE = 8.0

_torch = None
_device = None
_caption_processor = None
_caption_model = None
_classifier_processor = None
_classifier_model = None
_classifier_load_failed = False
_similarity_processor = None
_similarity_model = None
_similarity_load_failed = False


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


def _load_similarity_model():
    global _similarity_processor, _similarity_model, _similarity_load_failed

    if not ENABLE_SIMILARITY_RANKING or _similarity_load_failed:
        return None, None

    if _similarity_processor is None or _similarity_model is None:
        try:
            from transformers import CLIPModel, CLIPProcessor

            device = _get_device()
            _similarity_processor = CLIPProcessor.from_pretrained(SIMILARITY_MODEL)
            _similarity_model = CLIPModel.from_pretrained(SIMILARITY_MODEL).to(device)
            _similarity_model.eval()
        except Exception:
            _similarity_load_failed = True
            LOGGER.exception("Unable to load image-text similarity model")
            return None, None

    return _similarity_processor, _similarity_model


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

    return f"{_article_for(label)} {label} is visible"


def _classifier_label(image):
    processor, model = _load_classifier_model()
    if processor is None or model is None:
        return ""

    torch = _load_torch()
    inputs = processor(images=image, return_tensors="pt")
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        logits = model(**inputs).logits

    probabilities = torch.nn.functional.softmax(logits, dim=-1)[0].detach().cpu().tolist()
    return _label_from_classifier_scores(probabilities, model.config.id2label)


def _label_from_classifier_scores(scores, id2label, min_confidence=CLASSIFIER_MIN_CONFIDENCE):
    if not scores:
        return ""

    predicted_id, confidence = max(enumerate(scores), key=lambda item: item[1])
    if confidence < min_confidence:
        return ""

    label = id2label.get(predicted_id, "")
    return _clean_classifier_label(label)


def _classifier_caption(image):
    return _caption_from_label(_classifier_label(image))


def _caption_prompts(primary_label):
    prompts = [
        "a photo of",
        "a clear image of",
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


def _word_counts(candidates):
    counts = {}
    for candidate in candidates:
        for word in set(_caption_words(candidate)):
            counts[word] = counts.get(word, 0) + 1
    return counts


def _caption_evidence(candidates):
    word_counts = _word_counts(candidates)
    return {
        "words": word_counts,
        "actions": {word: word_counts.get(word, 0) for word in ACTION_WORDS},
        "important_objects": {
            word: word_counts.get(word, 0)
            for word in IMPORTANT_VISIBLE_WORDS
        },
        "scenes": {word: word_counts.get(word, 0) for word in SCENE_LABEL_WORDS},
    }


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


def _caption_score(caption, primary_label="", evidence=None):
    if _is_generic_caption(caption):
        return -100.0

    evidence = evidence or {}
    action_counts = evidence.get("actions") or {}
    scene_counts = evidence.get("scenes") or {}
    normalized = _normalized_caption(caption).lower()
    words = _caption_words(normalized)
    word_set = set(words)
    score = min(len(words), 18) * 0.18

    if len(words) < 5:
        score -= 2.0
    if len(words) >= 8:
        score += 1.0

    if normalized.startswith(("a photo of", "an image of", "a picture of")):
        score -= 1.2

    if primary_label and _caption_mentions_label(normalized, primary_label):
        score += 3.5
        position = _label_position(normalized, primary_label)
        if position is not None and position <= 5:
            score += 2.0
        elif position is not None and position > 8:
            score -= 1.5

    for word in word_set & ACTION_WORDS:
        if action_counts and action_counts.get(word, 0) >= 2:
            score += 1.5
        else:
            score -= 0.6

    if any(word in SCENE_WORDS for word in words):
        score += 1.0

    score += len(word_set & IMPORTANT_VISIBLE_WORDS) * 0.6

    unsupported_terms = (
        (word_set & UNSUPPORTED_RELATIONSHIP_TERMS)
        | (word_set & SUBJECTIVE_MODIFIERS)
        | (word_set & EVENT_GUESSES)
        | (word_set & VAGUE_WORDS)
        | (word_set & IMAGE_QUALITY_WORDS)
    )
    score -= len(unsupported_terms) * 1.4

    unsupported_scenes = {
        word
        for word in word_set & SCENE_LABEL_WORDS
        if scene_counts and scene_counts.get(word, 0) < 2
    }
    score -= len(unsupported_scenes) * 1.2

    if any(phrase in normalized for phrase in SPECULATIVE_PHRASES):
        score -= 2.0

    if normalized.startswith(BACKGROUND_FIRST_TERMS) or "background" in word_set:
        score -= 2.5

    return score


def _strip_prompt_lead(caption):
    caption = _normalized_caption(caption)
    caption = re.sub(
        r"^(?:the main subject(?: of the image)? is|this image shows|the image shows|the photo shows|this photo shows|there is|there are)\s+",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        r"^(?:a|an|the)\s+(?:photo|image|picture)\s+of\s+",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    return _normalized_caption(caption)


def _one_sentence(caption):
    caption = _normalized_caption(caption)
    match = re.match(r"^(.+?)(?:[.!?]+(?:\s|$)|$)", caption)
    if match:
        caption = match.group(1)
    return _normalized_caption(caption)


def _remove_speculative_language(caption):
    caption = _normalized_caption(caption)
    for phrase in SPECULATIVE_PHRASES:
        caption = re.sub(rf"\b{re.escape(phrase)}\b", "", caption, flags=re.IGNORECASE)
    return _normalized_caption(caption)


def _replace_relationship_claims(caption):
    replacements = {
        r"\b(?:his|her|their|the)\s+owner\b": "a person",
        r"\b(?:his|her|their|the)\s+(?:mother|father|parent|parents)\b": "an adult",
        r"\b(?:his|her|their|the)\s+(?:friend|friends)\b": "another person",
        r"\ba couple\b": "two people",
        r"\bfamily\b": "people",
    }
    for pattern, replacement in replacements.items():
        caption = re.sub(pattern, replacement, caption, flags=re.IGNORECASE)
    return caption


def _replace_vague_quantities(caption):
    caption = re.sub(
        r"\b(?:a\s+)?(?:group|bunch)\s+of\s+people\b",
        "people",
        caption,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        r"\b(?:many|several|various)\s+people\b",
        "people",
        caption,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        r"\b(?:a\s+)?(?:group|bunch)\s+of\s+([a-z]+s)\b",
        r"\1",
        caption,
        flags=re.IGNORECASE,
    )
    return _normalized_caption(caption)


def _remove_unsupported_modifiers(caption):
    for word in SUBJECTIVE_MODIFIERS | EVENT_GUESSES | VAGUE_WORDS | IMAGE_QUALITY_WORDS:
        caption = re.sub(rf"\b{re.escape(word)}\b", "", caption, flags=re.IGNORECASE)
    return _normalized_caption(caption)


def _remove_unsupported_scene_labels(caption, evidence=None):
    evidence = evidence or {}
    scene_counts = evidence.get("scenes") or {}

    def replace_scene(match):
        scene = match.group("scene").lower()
        if scene in IMPORTANT_VISIBLE_WORDS or (scene_counts and scene_counts.get(scene, 0) >= 2):
            return match.group(0)
        return ""

    scene_pattern = (
        r"\b(?:in|inside|at|near|outside|on)\s+"
        r"(?:a|an|the)?\s*(?P<scene>"
        + "|".join(sorted(SCENE_LABEL_WORDS))
        + r")\b"
    )
    caption = re.sub(scene_pattern, replace_scene, caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(?:in|at|near|toward)\s+the\s+background\b", "", caption, flags=re.IGNORECASE)
    return _normalized_caption(caption)


def _clean_caption_grammar(caption):
    caption = _normalized_caption(caption)
    caption = re.sub(r"\b(?:a\s+)?close[- ]?up\s+of\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(?:in|inside|within)\s+(?:the\s+)?(?:image|photo|picture)\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(?:shown|visible)\s+(?:in|inside|within)\s+(?:the\s+)?(?:image|photo|picture)\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\s+([,.;:])", r"\1", caption)
    caption = re.sub(r"\b(a|an|the)\s+([,.;:])", r"\2", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(with|near|beside|next to)\s*\.", ".", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(in|on|at|under|inside|outside)\s*\.", ".", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\s+", " ", caption).strip(" ,")
    return caption


def _make_caption_natural(caption):
    caption = _normalized_caption(caption)
    action_pattern = "|".join(sorted(ACTION_WORDS))

    if re.search(rf"\b(?:is|are|was|were)\s+(?:{action_pattern})\b", caption, flags=re.IGNORECASE):
        return caption

    caption = re.sub(
        rf"^((?:a|an|the)\s+.+?)\s+({action_pattern})(\b.*)$",
        r"\1 is \2\3",
        caption,
        count=1,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        rf"^((?:two|three|four|people)\s+.+?)\s+({action_pattern})(\b.*)$",
        r"\1 are \2\3",
        caption,
        count=1,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        rf"^(people)\s+({action_pattern})(\b.*)$",
        r"\1 are \2\3",
        caption,
        count=1,
        flags=re.IGNORECASE,
    )
    return _normalized_caption(caption)


def _sanitize_caption_claims(caption, evidence=None):
    caption = _one_sentence(caption)
    caption = _strip_prompt_lead(caption)
    caption = _remove_speculative_language(caption)
    caption = _replace_relationship_claims(caption)
    caption = _replace_vague_quantities(caption)
    caption = _remove_unsupported_modifiers(caption)
    caption = _remove_unsupported_scene_labels(caption, evidence)
    caption = _make_caption_natural(caption)
    return _clean_caption_grammar(caption)


def _finalize_caption(caption, primary_label="", evidence=None):
    caption = _sanitize_caption_claims(caption, evidence)

    if _is_generic_caption(caption) or len(_caption_words(caption)) < 4:
        caption = _caption_from_label(primary_label)
        caption = _sanitize_caption_claims(caption, evidence)

    caption = _normalized_caption(caption).strip(" .")
    if not caption:
        caption = "visible objects are present"

    return caption[:1].upper() + caption[1:] + "."


def _invalid_caption_reason(caption):
    normalized = _normalized_caption(caption).lower().strip(" .")
    words = _caption_words(normalized)

    if _is_generic_caption(normalized):
        return "generic"
    if not words:
        return "empty"
    if len(words) < 4:
        return "too_short"
    if len(words) > 30:
        return "too_long"
    if normalized.startswith(("a photo of", "an image of", "a picture of")):
        return "generic_media_prefix"
    if words[-1] in TRAILING_PREPOSITIONS:
        return "trailing_preposition"
    if re.search(r"\b([a-z]+)\s+\1\b", normalized):
        return "repeated_word"
    if not re.search(
        r"\b(is|are|with|near|beside|in|inside|on|outside|under|"
        r"carrying|eating|flying|holding|jumping|laying|lying|looking|"
        r"playing|riding|running|sitting|standing|walking|wearing|visible|present)\b",
        normalized,
    ):
        return "missing_predicate"

    return ""


def _image_text_similarity(image, captions):
    processor, model = _load_similarity_model()
    if processor is None or model is None or not captions:
        return {}

    torch = _load_torch()
    inputs = processor(
        text=captions,
        images=image,
        return_tensors="pt",
        padding=True,
        truncation=True,
    )
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        outputs = model(**inputs)

    scores = outputs.logits_per_image[0].detach().cpu().tolist()
    return dict(zip(captions, scores))


def _candidate_diagnostics(candidates, evidence):
    records = []
    seen = set()
    for raw_candidate in candidates:
        sanitized = _sanitize_caption_claims(raw_candidate, evidence)
        reason = _invalid_caption_reason(sanitized)
        if sanitized in seen and not reason:
            reason = "duplicate"
        if sanitized:
            seen.add(sanitized)
        records.append(
            {
                "raw": raw_candidate,
                "caption": sanitized,
                "rejected": bool(reason),
                "reason": reason,
            }
        )
    return records


def _best_caption(image, candidates, primary_label=""):
    evidence = _caption_evidence(candidates)
    diagnostics = _candidate_diagnostics(candidates, evidence)
    usable_candidates = [
        record["caption"]
        for record in diagnostics
        if not record["rejected"]
    ]

    if not usable_candidates:
        return "", diagnostics, {}

    similarities = _image_text_similarity(image, usable_candidates)

    best_caption = max(
        usable_candidates,
        key=lambda candidate: (
            similarities.get(candidate, 0.0),
            _caption_score(candidate, primary_label, evidence),
        ),
    )
    return best_caption, diagnostics, similarities


def image_file_hash(image_path):
    digest = hashlib.sha256()
    with open(image_path, "rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_caption_result(image_path):
    with Image.open(image_path) as uploaded_image:
        image = uploaded_image.convert("RGB")

    image_hash = image_file_hash(image_path)
    primary_label = _classifier_label(image)
    generation_attempts = (
        {
            "max_new_tokens": 24,
            "min_length": 8,
            "num_beams": 3,
            "repetition_penalty": 1.1,
            "length_penalty": 1.0,
            "early_stopping": True,
        },
        {
            "max_new_tokens": 32,
            "min_length": 10,
            "num_beams": 5,
            "repetition_penalty": 1.2,
            "length_penalty": 0.9,
            "early_stopping": True,
        },
        {
            "max_new_tokens": 36,
            "min_length": 10,
            "num_beams": 7,
            "repetition_penalty": 1.25,
            "length_penalty": 1.0,
            "early_stopping": True,
        },
    )

    candidates = []
    diagnostics = []
    similarities = {}
    for options in generation_attempts:
        for prompt in _caption_prompts(primary_label):
            caption = _generate_blip_caption(image, options, prompt=prompt)
            if caption and caption not in candidates:
                candidates.append(caption)

        best_caption, diagnostics, similarities = _best_caption(image, candidates, primary_label)
        evidence = _caption_evidence(candidates)
        if best_caption and _caption_score(best_caption, primary_label, evidence) >= STRONG_CAPTION_SCORE:
            english_caption = _finalize_caption(best_caption, primary_label, evidence)
            break
    else:
        best_caption, diagnostics, similarities = _best_caption(image, candidates, primary_label)
        if best_caption:
            english_caption = _finalize_caption(best_caption, primary_label, _caption_evidence(candidates))
        else:
            fallback_caption = _classifier_caption(image)
            if fallback_caption:
                english_caption = _finalize_caption(fallback_caption, primary_label)
            else:
                english_caption = "Visible objects are present."

    result = {
        "image_hash": image_hash,
        "generated_candidates": candidates,
        "candidate_diagnostics": diagnostics,
        "selected_english_caption": english_caption,
        "similarity_scores": similarities,
    }
    LOGGER.info(
        "caption image_hash=%s candidates=%r selected_english=%r similarity_scores=%r",
        image_hash,
        candidates,
        english_caption,
        similarities,
    )
    return result


def generate_caption(image_path):
    return generate_caption_result(image_path)["selected_english_caption"]

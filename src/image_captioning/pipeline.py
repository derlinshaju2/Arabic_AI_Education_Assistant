import hashlib
import logging
import os
import re

from PIL import Image, UnidentifiedImageError


LOGGER = logging.getLogger(__name__)

CAPTION_MODEL = os.environ.get("CAPTION_MODEL", "Salesforce/blip-image-captioning-base")

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
VISIBLE_OBJECT_WORDS = {
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
    "man",
    "men",
    "motorcycle",
    "motorcycles",
    "net",
    "nets",
    "person",
    "people",
    "road",
    "sheep",
    "street",
    "table",
    "train",
    "truck",
    "trucks",
    "vehicle",
    "vehicles",
    "woman",
    "women",
}
OBJECT_ALIASES = {
    "animal": {"animal", "animals"},
    "bicycle": {"bicycle", "bicycles", "bike", "bikes"},
    "bird": {"bird", "birds"},
    "boat": {"boat", "boats"},
    "bus": {"bus", "buses"},
    "car": {"car", "cars", "vehicle", "vehicles"},
    "cart": {"cart", "carts", "shopping cart", "shopping carts"},
    "cat": {"cat", "cats"},
    "cow": {"cow", "cows"},
    "dog": {"dog", "dogs"},
    "horse": {"horse", "horses"},
    "motorcycle": {"motorcycle", "motorcycles", "motorbike", "motorbikes"},
    "net": {"net", "nets", "fishing net", "fishing nets"},
    "person": {"person", "people", "man", "men", "woman", "women"},
    "sheep": {"sheep"},
    "truck": {"truck", "trucks"},
    "vehicle": {"vehicle", "vehicles"},
}
OBJECT_CANONICAL = {
    alias: canonical
    for canonical, aliases in OBJECT_ALIASES.items()
    for alias in aliases
}
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
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
SUBJECTIVE_MODIFIERS = {"adorable", "angry", "beautiful", "cute", "happy", "old", "sad", "scared", "young"}
EVENT_GUESSES = {"birthday", "ceremony", "concert", "festival", "party", "wedding"}
VAGUE_WORDS = {"bunch", "group", "many", "several", "something", "stuff", "thing", "things", "various"}
IMAGE_QUALITY_WORDS = {"blurry", "detailed", "quality", "realistic"}
TRAILING_PREPOSITIONS = {"at", "beside", "by", "in", "inside", "near", "of", "on", "outside", "under", "with"}

_torch = None
_device = None
_caption_processor = None
_caption_model = None


class ImageCaptioningError(RuntimeError):
    pass


class InvalidImageError(ValueError):
    pass


def _normalized_caption(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _caption_words(caption):
    return re.findall(r"[a-zA-Z]+", (caption or "").lower())


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


def _move_to_device(inputs):
    device = _get_device()
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in inputs.items()
    }


def image_file_hash(image_path):
    digest = hashlib.sha256()
    with open(image_path, "rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_valid_image(image_path):
    try:
        with Image.open(image_path) as uploaded_image:
            uploaded_image.verify()
    except (OSError, UnidentifiedImageError) as error:
        raise InvalidImageError("The uploaded file is not a valid image.") from error

    with Image.open(image_path) as uploaded_image:
        return uploaded_image.convert("RGB")


def _decode_outputs(processor, outputs):
    sequences = getattr(outputs, "sequences", outputs)
    decoded = processor.batch_decode(sequences, skip_special_tokens=True)
    captions = []
    for caption in decoded:
        normalized = _normalized_caption(caption)
        if normalized and normalized not in captions:
            captions.append(normalized)
    return captions


def _generate_blip_candidates(image, generation_options):
    torch = _load_torch()
    processor, model = _load_caption_model()
    inputs = processor(images=image, return_tensors="pt")
    inputs = _move_to_device(inputs)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            return_dict_in_generate=True,
            output_scores=True,
            **generation_options,
        )

    captions = _decode_outputs(processor, outputs)
    sequence_scores = getattr(outputs, "sequences_scores", None)
    if sequence_scores is None:
        return [(caption, 0.0) for caption in captions]

    scores = sequence_scores.detach().cpu().tolist()
    return [
        (caption, float(scores[index]) if index < len(scores) else 0.0)
        for index, caption in enumerate(captions)
    ]


def _strip_prompt_lead(caption):
    caption = _normalized_caption(caption)
    caption = re.sub(
        r"^(?:the main subject(?: of the image)? is|this image shows|the image shows|the photo shows|this photo shows|there is|there are)\s+",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        r"^(?:(?:a|an|the)\s+)?(?:clear\s+)?caption\s+of\s+",
        "",
        caption,
        flags=re.IGNORECASE,
    )
    caption = re.sub(
        r"^(?:(?:a|an|the)\s+)?(?:photo|image|picture)\s+of\s+",
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


def _clean_caption_grammar(caption):
    caption = _normalized_caption(caption)
    caption = re.sub(r"\b(?:a\s+)?close[- ]?up\s+of\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(?:in|inside|within)\s+(?:the\s+)?(?:image|photo|picture)\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(?:shown|visible)\s+(?:in|inside|within)\s+(?:the\s+)?(?:image|photo|picture)\b", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\s+([,.;:])", r"\1", caption)
    caption = re.sub(r"\b(a|an|the)\s+([,.;:])", r"\2", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\b(with|near|beside|next to|in|on|at|under|inside|outside)\s*$", "", caption, flags=re.IGNORECASE)
    caption = re.sub(r"\s+", " ", caption).strip(" ,")
    return caption


def _make_caption_natural(caption):
    caption = _normalized_caption(caption)
    action_pattern = "|".join(sorted(ACTION_WORDS))
    predicate_pattern = rf"{action_pattern}|visible|present|beside|in|inside|near|next to|on|outside|under|with"
    match = re.match(
        rf"^(?P<subject>.+?)(?:\s+(?P<auxiliary>is|are|was|were))?\s+"
        rf"(?P<predicate>{predicate_pattern})(?P<rest>\b.*)$",
        caption,
        flags=re.IGNORECASE,
    )
    if not match:
        return caption

    subject = match.group("subject")
    if re.search(r"\b(?:appear|appears|be|been|being|seem|seems|to)\b", subject, flags=re.IGNORECASE):
        return caption

    subject, number = _normalize_subject_number(subject)
    auxiliary = match.group("auxiliary")
    if number:
        if auxiliary and auxiliary.lower() in {"was", "were"}:
            auxiliary = "were" if number == "plural" else "was"
        else:
            auxiliary = "are" if number == "plural" else "is"

    if not auxiliary:
        return caption

    return _normalized_caption(
        f"{subject} {auxiliary} {match.group('predicate')}{match.group('rest')}"
    )


def _pluralize_noun(noun):
    lower = noun.lower()
    irregular = {
        "person": "people",
        "man": "men",
        "woman": "women",
        "child": "children",
        "sheep": "sheep",
    }
    if lower in irregular.values():
        return noun
    if lower in irregular:
        return irregular[lower]
    if lower not in OBJECT_ALIASES and lower.endswith("s"):
        return noun
    if lower.endswith("y") and lower[-2:-1] not in "aeiou":
        return noun[:-1] + "ies"
    if lower.endswith(("ch", "sh", "s", "x", "z")):
        return noun + "es"
    return noun + "s"


def _singularize_noun(noun):
    lower = noun.lower()
    irregular = {
        "people": "person",
        "men": "man",
        "women": "woman",
        "children": "child",
        "sheep": "sheep",
    }
    if lower in irregular:
        return irregular[lower]

    for singular in OBJECT_ALIASES:
        if _pluralize_noun(singular).lower() == lower:
            return singular
    return noun


def _normalize_subject_number(subject):
    subject = _normalized_caption(subject)
    words = re.findall(r"[a-zA-Z]+|\d+", subject.lower())
    if not words:
        return subject, ""

    first = words[0]
    number = ""
    if first in {"a", "an", "one"} or first == "1":
        number = "singular"
    elif first in NUMBER_WORDS and NUMBER_WORDS[first] > 1:
        number = "plural"
    elif first.isdigit() and int(first) > 1:
        number = "plural"
    elif " and " in subject.lower():
        number = "plural"
    elif first in {"children", "men", "people", "women"}:
        number = "plural"
    else:
        last = words[-1]
        if last in OBJECT_ALIASES:
            number = "singular"
        elif any(_pluralize_noun(noun).lower() == last for noun in OBJECT_ALIASES):
            number = "plural"

    simple_subject = not re.search(r"\b(?:and|of|with)\b", subject, flags=re.IGNORECASE)
    if number and simple_subject:
        subject = re.sub(
            r"([a-zA-Z]+)(\s*)$",
            lambda match: (
                _pluralize_noun(match.group(1))
                if number == "plural"
                else _singularize_noun(match.group(1))
            )
            + match.group(2),
            subject,
        )

    article_match = re.match(r"^(a|an)\s+([a-zA-Z]+)", subject, flags=re.IGNORECASE)
    if article_match:
        article = "an" if article_match.group(2).lower().startswith(tuple("aeiou")) else "a"
        subject = article + subject[article_match.end(1) :]

    return _normalized_caption(subject), number


def _sanitize_caption_claims(caption):
    caption = _one_sentence(caption)
    caption = _strip_prompt_lead(caption)
    caption = _make_caption_natural(caption)
    return _clean_caption_grammar(caption)


def _caption_object_words(caption):
    normalized = _normalized_caption(caption).lower()
    found = set()
    for alias, canonical in OBJECT_CANONICAL.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            found.add(canonical)
    return found


def _caption_count_claims(caption):
    normalized = _normalized_caption(caption).lower()
    claims = {}
    number_pattern = "|".join(NUMBER_WORDS)

    for alias, canonical in sorted(OBJECT_CANONICAL.items(), key=lambda item: len(item[0]), reverse=True):
        explicit = re.search(rf"\b(?P<count>\d+|{number_pattern})\s+{re.escape(alias)}\b", normalized)
        if explicit:
            count_text = explicit.group("count")
            claims[canonical] = int(count_text) if count_text.isdigit() else NUMBER_WORDS[count_text]
            continue

        if re.search(rf"\b(?:a|an|one)\s+{re.escape(alias)}\b", normalized):
            claims.setdefault(canonical, 1)

    return claims


def _candidate_evidence(candidates):
    object_counts = {}
    count_claims = {}
    action_counts = {}

    for candidate in candidates:
        for object_name in _caption_object_words(candidate):
            object_counts[object_name] = object_counts.get(object_name, 0) + 1
        for action in set(_caption_words(candidate)) & ACTION_WORDS:
            action_counts[action] = action_counts.get(action, 0) + 1
        for object_name, count in _caption_count_claims(candidate).items():
            count_counts = count_claims.setdefault(object_name, {})
            count_counts[count] = count_counts.get(count, 0) + 1

    return {
        "objects": object_counts,
        "actions": action_counts,
        "count_claims": count_claims,
    }


def _invalid_caption_reason(caption, evidence):
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

    count_claims = evidence.get("count_claims") or {}
    for object_name, claimed_count in _caption_count_claims(normalized).items():
        consensus_counts = count_claims.get(object_name) or {}
        if not consensus_counts:
            continue
        consensus_count, agreement = max(consensus_counts.items(), key=lambda item: item[1])
        if agreement >= 2 and consensus_count != claimed_count:
            return f"count_conflict:{object_name}:{claimed_count}_vs_{consensus_count}"

    if not re.search(
        r"\b(is|are|with|near|beside|in|inside|on|outside|under|"
        r"carrying|eating|flying|holding|jumping|laying|lying|looking|"
        r"playing|riding|running|sitting|standing|walking|wearing|visible|present)\b",
        normalized,
    ):
        return "missing_predicate"

    return ""


def _caption_score(caption, evidence, model_score=0.0):
    normalized = _normalized_caption(caption).lower()
    words = _caption_words(normalized)
    word_set = set(words)
    score = float(model_score) + min(len(words), 18) * 0.18

    if len(words) < 5:
        score -= 2.0
    if len(words) >= 8:
        score += 1.0

    score += len(word_set & VISIBLE_OBJECT_WORDS) * 0.7

    action_counts = evidence.get("actions") or {}
    for word in word_set & ACTION_WORDS:
        score += 1.2 if action_counts.get(word, 0) >= 2 else 0.2

    if any(word in SCENE_WORDS for word in words):
        score += 0.8

    unsupported_terms = (
        (word_set & UNSUPPORTED_RELATIONSHIP_TERMS)
        | (word_set & SUBJECTIVE_MODIFIERS)
        | (word_set & EVENT_GUESSES)
        | (word_set & VAGUE_WORDS)
        | (word_set & IMAGE_QUALITY_WORDS)
    )
    score -= len(unsupported_terms) * 1.4
    if "background" in word_set:
        score -= 3.0

    return score


def _finalize_caption(caption):
    caption = _sanitize_caption_claims(caption)
    caption = _normalized_caption(caption).strip(" .")
    if not caption:
        raise ImageCaptioningError("BLIP returned an empty caption.")

    return caption[:1].upper() + caption[1:] + "."


def _candidate_diagnostics(raw_candidates):
    sanitized_candidates = [
        _sanitize_caption_claims(candidate["caption"])
        for candidate in raw_candidates
    ]
    evidence = _candidate_evidence(sanitized_candidates)
    diagnostics = []
    seen = set()

    for candidate in raw_candidates:
        sanitized = _sanitize_caption_claims(candidate["caption"])
        reason = _invalid_caption_reason(sanitized, evidence)
        if sanitized in seen and not reason:
            reason = "duplicate"
        if sanitized:
            seen.add(sanitized)
        diagnostics.append(
            {
                "raw": candidate["caption"],
                "caption": sanitized,
                "model_score": candidate["model_score"],
                "score": _caption_score(sanitized, evidence, candidate["model_score"]),
                "rejected": bool(reason),
                "reason": reason,
            }
        )

    return diagnostics, evidence


def _select_best_caption(raw_candidates):
    diagnostics, evidence = _candidate_diagnostics(raw_candidates)
    usable = [candidate for candidate in diagnostics if not candidate["rejected"]]
    if not usable:
        raise ImageCaptioningError("BLIP did not produce a usable caption.")

    return max(usable, key=lambda candidate: candidate["score"]), diagnostics, evidence


def generate_caption_result(image_path):
    image = load_valid_image(image_path)
    image_hash = image_file_hash(image_path)
    generation_attempts = (
        {
            "max_new_tokens": 30,
            "num_beams": 5,
            "num_return_sequences": 3,
            "repetition_penalty": 1.1,
            "length_penalty": 1.0,
            "early_stopping": True,
        },
        {
            "max_new_tokens": 36,
            "num_beams": 7,
            "num_return_sequences": 4,
            "repetition_penalty": 1.15,
            "length_penalty": 0.95,
            "early_stopping": True,
        },
    )
    raw_candidates = []
    seen = set()
    for options in generation_attempts:
        for caption, model_score in _generate_blip_candidates(image, options):
            if caption and caption not in seen:
                seen.add(caption)
                raw_candidates.append({"caption": caption, "model_score": model_score})

    selected, diagnostics, evidence = _select_best_caption(raw_candidates)
    english_caption = _finalize_caption(selected["caption"])
    if not english_caption.strip(". "):
        raise ImageCaptioningError("BLIP returned an empty caption.")

    result = {
        "image_hash": image_hash,
        "generated_candidates": [candidate["caption"] for candidate in raw_candidates],
        "candidate_diagnostics": diagnostics,
        "caption_evidence": evidence,
        "selected_english_caption": english_caption,
    }
    LOGGER.info(
        "caption image_hash=%s candidates=%r selected_english=%r evidence=%r",
        image_hash,
        result["generated_candidates"],
        english_caption,
        evidence,
    )
    return result


def generate_caption(image_path):
    return generate_caption_result(image_path)["selected_english_caption"]

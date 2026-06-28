import torch

MODEL = "Helsinki-NLP/opus-mt-en-ar"

_tokenizer = None
_model = None

NOUNS = {
    "adult": "بالغ",
    "airplane": "طائرة",
    "bird": "طائر",
    "bus": "حافلة",
    "car": "سيارة",
    "cat": "قطة",
    "child": "طفل",
    "dog": "كلب",
    "food": "طعام",
    "man": "رجل",
    "person": "شخص",
    "people": "أشخاص",
    "table": "طاولة",
    "train": "قطار",
    "tree": "شجرة",
    "woman": "امرأة",
}

ACTIONS = {
    "carrying": "يحمل",
    "eating": "يأكل",
    "flying": "يطير",
    "holding": "يمسك",
    "jumping": "يقفز",
    "laying": "مستلقي",
    "lying": "مستلقي",
    "looking": "ينظر",
    "playing": "يلعب",
    "riding": "يركب",
    "running": "يركض",
    "sitting": "جالس",
    "standing": "واقف",
    "walking": "يمشي",
    "wearing": "يرتدي",
}

PHRASES = {
    "in the grass": "على العشب",
    "on the grass": "على العشب",
    "with a person": "مع شخص",
    "with another person": "مع شخص آخر",
    "with two people": "مع شخصين",
    "near a person": "بالقرب من شخص",
    "on a table": "على طاولة",
    "in a room": "في غرفة",
    "on a street": "في شارع",
    "outdoors": "في الخارج",
}


def _load_model():
    global _tokenizer, _model

    if _tokenizer is None or _model is None:
        from transformers import MarianMTModel, MarianTokenizer

        _tokenizer = MarianTokenizer.from_pretrained(MODEL)
        _model = MarianMTModel.from_pretrained(MODEL)
        _model.eval()

    return _tokenizer, _model


def _normalize_source(text):
    return " ".join((text or "").strip().split())


def _strip_article(text):
    text = text.strip().lower()
    for article in ("a ", "an ", "the "):
        if text.startswith(article):
            return text[len(article) :]
    return text


def _noun_to_arabic(noun):
    noun = _strip_article(noun)
    return NOUNS.get(noun)


def _photo_of(noun):
    if not noun:
        return ""

    return f"صورة ل{noun}."


def _translate_rest(rest):
    rest = _normalize_source(rest).lower().strip(" .")
    if not rest:
        return ""

    translated = PHRASES.get(rest)
    if translated:
        return f" {translated}"

    return ""


def _template_translate(text):
    import re

    source = _normalize_source(text).strip()
    sentence = source.rstrip(".")
    lower = sentence.lower()

    match = re.match(r"^a photo of (?:a|an|the)?\s*(?P<noun>[a-z ]+)$", lower)
    if match:
        noun = _noun_to_arabic(match.group("noun"))
        if noun:
            return _photo_of(noun)

    match = re.match(
        r"^(?:a|an|the)\s+(?P<noun>[a-z ]+?)\s+"
        r"(?P<action>carrying|eating|flying|holding|jumping|laying|lying|looking|playing|riding|running|sitting|standing|walking|wearing)"
        r"(?P<rest>\s+.+)?$",
        lower,
    )
    if match:
        noun = _noun_to_arabic(match.group("noun"))
        action = ACTIONS.get(match.group("action"))
        rest = _translate_rest(match.group("rest") or "")
        if noun and action and (not match.group("rest") or rest):
            return f"{noun} {action}{rest}."

    return ""


def translate_to_arabic(text):
    if not text:
        return ""

    text = _normalize_source(text)

    template_translation = _template_translate(text)
    if template_translation:
        return template_translation

    tokenizer, model = _load_model()
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

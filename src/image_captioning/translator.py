import torch

MODEL = "Helsinki-NLP/opus-mt-en-ar"

_tokenizer = None
_model = None

NOUNS = {
    "animal": "\u062d\u064a\u0648\u0627\u0646",
    "cart": "\u0639\u0631\u0628\u0629",
    "cow": "\u0628\u0642\u0631\u0629",
    "sheep": "\u062e\u0631\u0648\u0641",
    "street": "\u0634\u0627\u0631\u0639",
    "vehicle": "\u0645\u0631\u0643\u0628\u0629",
    "adult": "بالغ",
    "airplane": "طائرة",
    "backpack": "حقيبة ظهر",
    "ball": "كرة",
    "bicycle": "دراجة",
    "bird": "طائر",
    "boat": "قارب",
    "book": "كتاب",
    "bottle": "زجاجة",
    "building": "مبنى",
    "bus": "حافلة",
    "car": "سيارة",
    "cat": "قطة",
    "chair": "كرسي",
    "child": "طفل",
    "couch": "أريكة",
    "cup": "كوب",
    "dog": "كلب",
    "food": "طعام",
    "grass": "عشب",
    "horse": "حصان",
    "laptop": "حاسوب محمول",
    "man": "رجل",
    "motorcycle": "دراجة نارية",
    "person": "شخص",
    "people": "أشخاص",
    "phone": "هاتف",
    "road": "طريق",
    "sky": "سماء",
    "snow": "ثلج",
    "table": "طاولة",
    "train": "قطار",
    "tree": "شجرة",
    "truck": "شاحنة",
    "water": "ماء",
    "woman": "امرأة",
}

ADJECTIVES = {
    "black": "أسود",
    "blue": "أزرق",
    "brown": "بني",
    "green": "أخضر",
    "large": "كبير",
    "red": "أحمر",
    "small": "صغير",
    "white": "أبيض",
    "yellow": "أصفر",
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

PLURAL_ACTIONS = {
    "carrying": "يحملون",
    "eating": "يأكلون",
    "flying": "يطيرون",
    "holding": "يمسكون",
    "jumping": "يقفزون",
    "laying": "مستلقيون",
    "lying": "مستلقيون",
    "looking": "ينظرون",
    "playing": "يلعبون",
    "riding": "يركبون",
    "running": "يركضون",
    "sitting": "جالسون",
    "standing": "واقفون",
    "walking": "يمشون",
    "wearing": "يرتدون",
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

FALLBACK_CAPTIONS = {
    "visible objects are present": "\u062a\u0648\u062c\u062f \u0623\u0634\u064a\u0627\u0621 \u0645\u0631\u0626\u064a\u0629.",
    "a photo with visible objects": "صورة تحتوي على أشياء مرئية.",
}

PREPOSITIONS = {
    "beside": "بجانب",
    "in": "في",
    "inside": "داخل",
    "near": "بالقرب من",
    "on": "على",
    "outside": "خارج",
    "under": "تحت",
    "with": "مع",
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
    if noun in NOUNS:
        return NOUNS[noun]

    words = noun.split()
    if len(words) > 1 and words[-1] in NOUNS:
        translated_adjectives = [
            ADJECTIVES[word]
            for word in words[:-1]
            if word in ADJECTIVES
        ]
        if len(translated_adjectives) == len(words[:-1]):
            return " ".join([NOUNS[words[-1]]] + translated_adjectives)

    return ""


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

    import re

    match = re.match(
        r"^(?P<prep>beside|in|inside|near|on|outside|under|with)\s+"
        r"(?P<noun>(?:a|an|the)?\s*[a-z ]+)$",
        rest,
    )
    if match:
        preposition = PREPOSITIONS.get(match.group("prep"))
        noun = _noun_to_arabic(match.group("noun"))
        if preposition and noun:
            return f" {preposition} {noun}"

    return ""


def _template_translate(text):
    import re

    source = _normalize_source(text).strip()
    sentence = source.rstrip(".")
    lower = sentence.lower()

    fallback = FALLBACK_CAPTIONS.get(lower)
    if fallback:
        return fallback

    match = re.match(r"^a photo of (?:a|an|the)?\s*(?P<noun>[a-z ]+)$", lower)
    if match:
        noun = _noun_to_arabic(match.group("noun"))
        if noun:
            return _photo_of(noun)

    match = re.match(r"^people\s+are\s+visible$", lower)
    if match:
        return "\u064a\u0638\u0647\u0631 \u0623\u0634\u062e\u0627\u0635."

    match = re.match(r"^(?:a|an|the)\s+(?P<noun>[a-z ]+?)\s+is\s+visible$", lower)
    if match:
        noun = _noun_to_arabic(match.group("noun"))
        if noun:
            return f"\u064a\u0638\u0647\u0631 {noun}."

    match = re.match(
        r"^(?P<noun>people)\s+"
        r"(?:(?:are)\s+)?"
        r"(?P<action>carrying|eating|flying|holding|jumping|laying|lying|looking|playing|riding|running|sitting|standing|walking|wearing)"
        r"(?P<rest>\s+.+)?$",
        lower,
    )
    if match:
        noun = _noun_to_arabic(match.group("noun"))
        action = PLURAL_ACTIONS.get(match.group("action"))
        rest = _translate_rest(match.group("rest") or "")
        if noun and action and (not match.group("rest") or rest):
            return f"{noun} {action}{rest}."

    match = re.match(
        r"^(?:a|an|the)\s+(?P<noun>[a-z ]+?)\s+"
        r"(?:(?:is|are)\s+)?"
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

import re
import string

arabic_stopwords = {
    "في", "من", "على", "إلى", "عن",
    "و", "يا", "أن", "إن", "كان",
    "ما", "هذا", "هذه", "هو", "هي",
    "هم", "هن", "كما", "قد", "لا",
    "لم", "لن"
}


def normalize_arabic(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)

    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ـ", "", text)

    return text


def remove_punctuation(text):
    arabic_punct = "؟،؛«»"
    all_punct = string.punctuation + arabic_punct
    return text.translate(str.maketrans('', '', all_punct))


def tokenize(text):
    return text.split()


def remove_stopwords(tokens):
    return [w for w in tokens if w not in arabic_stopwords]


def preprocess_text(text):
    if not text:
        return ""

    text = normalize_arabic(text)
    text = remove_punctuation(text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = tokenize(text)
    tokens = remove_stopwords(tokens)

    return " ".join(tokens)
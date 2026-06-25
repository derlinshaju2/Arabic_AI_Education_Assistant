import re
import string


BASE_ARABIC_STOPWORDS = {
    "\u0641\u064a", "\u0645\u0646", "\u0639\u0644\u0649", "\u0625\u0644\u0649", "\u0639\u0646",
    "\u0648", "\u064a\u0627", "\u0623\u0646", "\u0625\u0646", "\u0643\u0627\u0646",
    "\u0645\u0627", "\u0647\u0630\u0627", "\u0647\u0630\u0647", "\u0647\u0648", "\u0647\u064a",
    "\u0647\u0645", "\u0647\u0646", "\u0643\u0645\u0627", "\u0642\u062f", "\u0644\u0627",
    "\u0644\u0645", "\u0644\u0646",
}


def normalize_arabic(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(r"[\u0617-\u061A\u064B-\u0652]", "", text)
    text = re.sub(r"[\u0625\u0623\u0622\u0627]", "\u0627", text)
    text = re.sub(r"\u0649", "\u064a", text)
    text = re.sub(r"\u0624", "\u0648", text)
    text = re.sub(r"\u0626", "\u064a", text)
    text = re.sub(r"\u0629", "\u0647", text)
    text = re.sub(r"\u0640", "", text)

    return text


arabic_stopwords = {normalize_arabic(word) for word in BASE_ARABIC_STOPWORDS}


def remove_punctuation(text):
    arabic_punct = "\u061f\u060c\u061b\u00ab\u00bb"
    all_punct = string.punctuation + arabic_punct
    return text.translate(str.maketrans("", "", all_punct))


def tokenize(text):
    return text.split()


def remove_stopwords(tokens):
    return [word for word in tokens if word not in arabic_stopwords]


def preprocess_text(text):
    if not text:
        return ""

    text = normalize_arabic(text)
    text = remove_punctuation(text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = tokenize(text)
    tokens = remove_stopwords(tokens)

    return " ".join(tokens)

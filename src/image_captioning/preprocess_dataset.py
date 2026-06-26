import re

def load_captions(path):
    mapping = {}

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:

            # skip header
            if line.startswith("image_name"):
                continue

            parts = line.strip().split("|")

            # safety check
            if len(parts) != 3:
                continue

            img, _, caption = parts

            if not caption:
                continue

            # normalize
            caption = caption.lower()

            # remove unwanted characters (keep letters + spaces)
            caption = re.sub(r"[^a-z\s]", "", caption)

            # remove extra spaces
            caption = re.sub(r"\s+", " ", caption).strip()

            if len(caption) == 0:
                continue

            # add sequence tokens
            caption = "startseq " + caption + " endseq"

            if img not in mapping:
                mapping[img] = []

            mapping[img].append(caption)

    return mapping


# -------------------------
# TEST
# -------------------------
if __name__ == "__main__":

    captions = load_captions("dataset/captions.txt")

    print("Total images:", len(captions))

    first_key = list(captions.keys())[0]
    print("Sample image:", first_key)
    print("Captions:", captions[first_key])
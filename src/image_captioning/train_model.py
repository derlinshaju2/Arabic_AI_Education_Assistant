import numpy as np
import pickle
import tensorflow as tf
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, LSTM, Embedding, Dropout, add

# -------------------------
# Load features
# -------------------------
features = np.load("features/image_features.npy", allow_pickle=True).item()

# -------------------------
# Load captions
# -------------------------
def load_captions(path):
    mapping = {}

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:

            if line.startswith("image_name"):
                continue

            parts = line.strip().split("|")

            if len(parts) != 3:
                continue

            img, _, caption = parts

            caption = caption.lower()
            caption = "startseq " + caption + " endseq"

            mapping.setdefault(img, []).append(caption)

    return mapping


captions = load_captions("dataset/captions.txt")

# -------------------------
# Tokenizer
# -------------------------
all_captions = [cap for caps in captions.values() for cap in caps]

tokenizer = Tokenizer()
tokenizer.fit_on_texts(all_captions)

vocab_size = len(tokenizer.word_index) + 1
print("Vocab size:", vocab_size)

pickle.dump(tokenizer, open("models/tokenizer.pkl", "wb"))

# -------------------------
# Max length
# -------------------------
max_length = max(len(c.split()) for c in all_captions)
print("Max length:", max_length)

# -------------------------
# Generator
# -------------------------
def gen():
    for img, caps in captions.items():

        if img not in features:
            continue

        feature = features[img]

        # FIX: ensure correct shape
        if feature.ndim == 3 or feature.ndim == 1:
            feature = feature.reshape(-1)

        for cap in caps:
            seq = tokenizer.texts_to_sequences([cap])[0]

            for i in range(1, len(seq)):
                in_seq = seq[:i]
                out_seq = seq[i]

                in_seq = pad_sequences([in_seq], maxlen=max_length)[0]

                yield (
                    (
                        np.array(feature, dtype=np.float32),
                        np.array(in_seq, dtype=np.int32)
                    ),
                    np.array(out_seq, dtype=np.int32)
                )

# -------------------------
# Dataset
# -------------------------
dataset = tf.data.Dataset.from_generator(
    gen,
    output_signature=(
        (
            tf.TensorSpec(shape=(4096,), dtype=tf.float32),
            tf.TensorSpec(shape=(max_length,), dtype=tf.int32)
        ),
        tf.TensorSpec(shape=(), dtype=tf.int32)
    )
)

# 🔥 IMPORTANT FIXES
dataset = dataset.shuffle(1000).batch(64).prefetch(tf.data.AUTOTUNE)

# -------------------------
# Model
# -------------------------
inputs1 = Input(shape=(4096,))
fe1 = Dropout(0.4)(inputs1)
fe2 = Dense(256, activation='relu')(fe1)

inputs2 = Input(shape=(max_length,))
se1 = Embedding(vocab_size, 256, mask_zero=True)(inputs2)
se2 = LSTM(256)(se1)

decoder1 = add([fe2, se2])
decoder2 = Dense(256, activation='relu')(decoder1)
outputs = Dense(vocab_size, activation='softmax')(decoder2)

model = Model(inputs=[inputs1, inputs2], outputs=outputs)

model.compile(
    loss='sparse_categorical_crossentropy',
    optimizer='adam'
)

model.summary()

# -------------------------
# Train
# -------------------------
model.fit(
    dataset,
    epochs=20,   # 🔥 increased
    steps_per_epoch=2000
)

# -------------------------
# Save
# -------------------------
model.save("models/caption_model.keras")

print("Model trained and saved successfully!")
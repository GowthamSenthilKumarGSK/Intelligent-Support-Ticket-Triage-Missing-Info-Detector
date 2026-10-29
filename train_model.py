import os
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import classification_report

DATA = "data/tickets_ready.csv"
EMBED_FILE = "data/embeddings.npy"
MODEL_NAME = "BAAI/bge-base-en-v1.5"

os.makedirs("models", exist_ok=True)

df = pd.read_csv(DATA)

# embedding 900 tickets takes a few minutes on CPU, so save the result and reuse it
if os.path.exists(EMBED_FILE):
    vectors = np.load(EMBED_FILE)
    assert len(vectors) == len(df), "embeddings.npy is out of date, delete it and rerun"
else:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer(MODEL_NAME)
    embedder.max_seq_length = 256
    vectors = embedder.encode(df["model_text"].tolist(), batch_size=16,
                              show_progress_bar=True, normalize_embeddings=True)
    np.save(EMBED_FILE, vectors)

# only the train split is used to learn; pending_gold and demo stay untouched
is_train = (df["split"] == "train").values
X = vectors[is_train]


def train_head(labels, name):
    y = labels[is_train]
    head = LogisticRegression(max_iter=2000, class_weight="balanced")

    # 5-fold check on the training rows, so we see how well it does on unseen tickets
    guesses = cross_val_predict(head, X, y, cv=5)
    print("\n==", name, "(5-fold on train) ==")
    print(classification_report(y, guesses, digits=3))

    head.fit(X, y)
    joblib.dump(head, f"models/{name}_head.joblib")


train_head(df["team"].values, "team")
train_head(df["priority"].values, "priority")
print("saved heads to models/")
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

DATA = "data/tickets_ready.csv"
EMBED_FILE = "data/embeddings.npy"
OUT_FILE = "models/thresholds.json"
ALPHA = 0.10      # we want the true label inside the set about 90% of the time
K = 5             # how many similar past tickets vote


def find_threshold(probs, y_true, classes, alpha=ALPHA):
    # for every held-out ticket: how unsure was the model about the TRUE label?
    true_index = [list(classes).index(label) for label in y_true]
    scores = 1 - probs[np.arange(len(y_true)), true_index]
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


def label_set(probs_row, classes, threshold):
    # every label that is not too unlikely
    return [c for c, p in zip(classes, probs_row) if 1 - p <= threshold]


def set_status(labels):
    if len(labels) == 1:
        return "confident"
    if len(labels) == 0:
        return "out_of_distribution"
    return "ambiguous"


def nearest_tickets(vector, train_vectors, train_labels, k=K):
    # vectors are normalised, so a dot product is the cosine similarity
    sims = train_vectors @ vector
    top = np.argsort(sims)[::-1][:k]
    votes = {}
    for i in top:
        votes[train_labels[i]] = votes.get(train_labels[i], 0) + sims[i]
    best_label = max(votes, key=votes.get)
    return best_label, float(sims[top[0]]), top


def calibrate():
    df = pd.read_csv(DATA)
    vectors = np.load(EMBED_FILE)
    is_train = (df["split"] == "train").values
    X = vectors[is_train]

    thresholds = {}
    for name in ["team", "priority"]:
        y = df[name].values[is_train]
        head = LogisticRegression(max_iter=2000, class_weight="balanced")
        probs = cross_val_predict(head, X, y, cv=5, method="predict_proba")
        classes = list(np.unique(y))
        thresholds[name] = find_threshold(probs, y, classes)

    # how close is a ticket to its nearest OTHER training ticket?
    sims = X @ X.T
    np.fill_diagonal(sims, -1)
    closest = sims.max(axis=1)
    thresholds["low_similarity"] = float(np.percentile(closest, 5))

    with open(OUT_FILE, "w") as f:
        json.dump(thresholds, f, indent=2)
    return thresholds


if __name__ == "__main__":
    thresholds = calibrate()
    print("thresholds:", thresholds)

    # quick look at tickets the model has not trained on (labels are not used here)
    df = pd.read_csv(DATA)
    vectors = np.load(EMBED_FILE)
    team_head = joblib.load("models/team_head.joblib")
    other = (df["split"] != "train").values
    probs = team_head.predict_proba(vectors[other])
    statuses = [set_status(label_set(p, team_head.classes_, thresholds["team"])) for p in probs]
    print()
    print(pd.Series(statuses).value_counts())

    train_vectors = vectors[(df["split"] == "train").values]
    closest = (vectors[other] @ train_vectors.T).max(axis=1)
    share_low = (closest < thresholds["low_similarity"]).mean()
    print("share of unseen tickets that look unlike any training ticket:", round(share_low, 3))
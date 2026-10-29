import json
import numpy as np
import pandas as pd
import joblib
from sentence_transformers import SentenceTransformer

from signals import extract_signals, mask_noise
from rules import priority_floor, assign_level
from confidence import label_set, set_status, nearest_tickets
from guard import run_guard

DATA = "data/tickets_ready.csv"
EMBED_FILE = "data/embeddings.npy"

# loaded once when the file is imported
df = pd.read_csv(DATA)
vectors = np.load(EMBED_FILE)
is_train = (df["split"] == "train").values
train_df = df[is_train].reset_index(drop=True)
train_vectors = vectors[is_train]

team_head = joblib.load("models/team_head.joblib")
priority_head = joblib.load("models/priority_head.joblib")
with open("models/thresholds.json") as f:
    thresholds = json.load(f)

embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
embedder.max_seq_length = 256


def triage_ticket(title, body):
    text = (str(title or "") + "\n" + str(body or "")).strip()
    signals = extract_signals(text)

    # edge case: nothing useful to work with
    if signals["word_count"] < 4:
        return {
            "status": "Needs Clarification",
            "team": None, "priority": None, "level": None,
            "reasons": ["the ticket is too short to triage"],
            "checklist": ["Describe the problem in a few sentences: what you did, what you expected, what happened."],
            "similar": [],
        }

    vector = embedder.encode([mask_noise(text)], normalize_embeddings=True)[0]

    # team, with confidence
    team_probs = team_head.predict_proba([vector])[0]
    team = team_head.classes_[team_probs.argmax()]
    team_options = label_set(team_probs, team_head.classes_, thresholds["team"])
    team_status = set_status(team_options)

    # similar past tickets
    _, closest, top = nearest_tickets(vector, train_vectors, train_df["team"].values)
    similar = [train_df["title"].iloc[i] for i in top[:3]]

    # level: rules
    level, level_reason = assign_level(text)

    # edge case: unlike anything we have seen, no clear team, and no technical cue at all
    no_cue = level_reason.startswith("no rule matched")
    if no_cue and closest < thresholds["low_similarity"] and team_probs.max() < 0.5:
        return {
            "status": "Needs Clarification",
            "team": None, "priority": None, "level": None,
            "reasons": ["the ticket does not look like a support request for any of our teams"],
            "checklist": ["If this is a real support issue, name the product and describe what went wrong."],
            "similar": [],
        }

    # priority: model first, then the safety floor
    model_priority = priority_head.predict([vector])[0]
    priority, priority_reason = priority_floor(text, model_priority)

    # a how-to question has no service impact, so the model alone cannot make it P1
    if level == "L1" and priority == "P1" and priority_reason == "model prediction":
        priority, priority_reason = "P3", "how-to question, capped at P3 (low urgency)"

    # the guard decides the final status
    result = run_guard(text, team, level, team_status, closest,
                       thresholds["low_similarity"], priority, priority_reason)

    # a default level is a guess, so say so
    if level_reason.startswith("no rule matched") and result["status"].startswith("Routed"):
        result["status"] = result["status"].replace(" (low confidence, please review)", "")
        result["status"] += " (level unclear, please review)"
        result["reasons"] = result["reasons"] + ["no level rule matched, L2 is only a default"]

    result.update({
        "team": team,
        "team_confidence": round(float(team_probs.max()), 2),
        "team_options": team_options,
        "team_status": team_status,
        "priority": priority,
        "priority_reason": priority_reason,
        "level": level,
        "level_reason": level_reason,
        "closest_similarity": round(closest, 2),
        "similar": similar,
    })
    return result


if __name__ == "__main__":
    tests = [
        ("", ""),
        ("broken", ""),
        ("Login fails", "invalid_grant on staging, Chrome 126 on Windows 11.\nSteps to reproduce:\n1. open the app\n2. click sign in\n3. see the error page"),
        ("App crashes", "It crashes sometimes, please fix."),
        ("Pizza order", "I want to order a large pizza with extra cheese for delivery tonight."),
        ("Database deadlock in nightly pipeline", "The nightly job hits a deadlock sometimes and the load never finishes."),
    ]
    for title, body in tests:
        print(repr(title), "->", triage_ticket(title, body))
        print()
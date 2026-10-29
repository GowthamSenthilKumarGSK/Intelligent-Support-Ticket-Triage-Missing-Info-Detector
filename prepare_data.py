import pandas as pd
from signals import extract_signals, mask_noise

INPUT = "data/tickets_clean.csv"
OUTPUT = "data/tickets_ready.csv"

df = pd.read_csv(INPUT)
print("rows loaded:", len(df))

# every ticket needs some text to learn from
df["text"] = df["text"].fillna("").astype(str)
df = df[df["text"].str.split().str.len() >= 3].copy()
print("rows after dropping near-empty tickets:", len(df))

# signals are read from the raw text, the model sees the masked text
signal_rows = [extract_signals(t) for t in df["text"]]
for name in ["has_error_code", "has_environment", "has_repro_steps", "has_logs", "has_stack_trace"]:
    df[name] = [row[name] for row in signal_rows]
df["word_count"] = [row["word_count"] for row in signal_rows]

df["model_text"] = df["text"].apply(mask_noise)

df.to_csv(OUTPUT, index=False)

print()
print(df["split"].value_counts())
print()
print(df["team"].value_counts())
print()
print(df["priority"].value_counts())
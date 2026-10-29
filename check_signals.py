import pandas as pd
from signals import extract_signals


df = pd.read_csv("data/tickets_clean.csv")
df["text"] = df["text"].fillna("").astype(str)

signals = pd.DataFrame(
    df["text"].apply(extract_signals).tolist(),
    index=df.index,
)

# Use tickets with at least one issue-template section.
templated = pd.to_numeric(
    df["tpl_n_sections"], errors="coerce"
).fillna(0) > 0

comparisons = [
    ("has_environment", "tpl_has_env"),
    ("has_repro_steps", "tpl_has_repro"),
    ("has_logs", "tpl_has_logs"),
]


def to_bool(series):
    """Convert common boolean representations into True/False."""
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
            "1": True,
            "0": False,
            "yes": True,
            "no": False,
        })
    )


for predicted_col, expected_col in comparisons:
    predicted = signals[predicted_col]
    expected = to_bool(df[expected_col])

    # Exclude missing or unrecognized template annotations.
    valid = templated & expected.notna()

    predicted = predicted[valid].astype(bool)
    expected = expected[valid].astype(bool)

    if len(expected) == 0:
        print(f"\n{predicted_col}: no usable template annotations")
        continue

    true_positive = (predicted & expected).sum()
    false_positive = (predicted & ~expected).sum()
    false_negative = (~predicted & expected).sum()

    agreement = (predicted == expected).mean()

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive else 0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative else 0
    )

    print(f"\n{predicted_col}")
    print(f"  Evaluated tickets: {len(expected)}")
    print(f"  Agreement:         {agreement:.2f}")
    print(f"  Precision:         {precision:.2f}")
    print(f"  Recall:            {recall:.2f}")


print(
    "\nTickets with an error code or exception name:",
    f"{signals['has_error_code'].mean():.2f}",
)

print(
    "Tickets with a stack trace:",
    f"{signals['has_stack_trace'].mean():.2f}",
)
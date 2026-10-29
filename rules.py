import re
from signals import extract_signals, mentions

# Priority = how urgent for the business. Level = how deep the technical work is.
# They are separate: a login outage for everyone is P1 but may still be an L2 job.

# Phrases that always mean P1, whatever the model says.
# Based on the usual ITIL idea: P1 = critical impact (service down, data lost, security hit).
P1_PHRASES = [
    "production down", "production is down", "site is down", "service is down",
    "outage", "data loss", "lost data", "data corruption",
    "all users affected", "affects all users", "affecting all users", "every user is affected",
    "security breach", "data breach", "data leak",
    "remote code execution", "unauthorized access",
]

# Level L3: needs a developer to look at the code
L3_PHRASES = [
    "segfault", "segmentation fault", "memory leak", "race condition", "deadlock",
    "data corruption", "regression", "core dumped", "kernel panic", "vulnerability",
    "remote code execution", "crash",
]

# Level L1: a question or a how-to, answered from documentation
L1_PATTERNS = [
    r"\bhow (do|can|to|should)\b",
    r"\bis it possible\b",
    r"\bwhere (can|do|is)\b",
    r"\breset (my )?password\b",
    r"\bdocumentation\b",
    r"\btypo\b",
    r"\bfeature request\b",
]

# Level L2: setup, configuration or integration problem someone must investigate
L2_PHRASES = [
    "config", "configuration", "setting", "permission", "timeout", "install",
    "upgrade", "after updating", "proxy", "certificate", "environment variable",
    "does not work", "doesn't work", "not working", "fails", "failed", "failure",
]


def priority_floor(text, model_priority):
    # if the text says something critical, P1 wins over the model's guess
    for phrase in P1_PHRASES:
        if mentions(text, phrase):
            return "P1", f"floor rule: '{phrase}'"
    return model_priority, "model prediction"


def assign_level(text):
    # order matters: the deepest level that applies wins
    signals = extract_signals(text)

    # 1. L3 first: a stack trace or a code-level problem word
    if signals["has_stack_trace"]:
        return "L3", "stack trace in the ticket"
    for phrase in L3_PHRASES:
        if mentions(text, phrase):
            return "L3", f"code-level problem: '{phrase}'"

    # 2. L2 next: setup or configuration problem
    for phrase in L2_PHRASES:
        if mentions(text, phrase):
            return "L2", f"setup/config problem: '{phrase}'"

    # 3. L1: a question or how-to
    lower = text.lower()
    for pattern in L1_PATTERNS:
        if re.search(pattern, lower):
            return "L1", "question / how-to"

    # nothing matched: the middle level is the safest guess, and we say so
    return "L2", "no rule matched, default to L2"


if __name__ == "__main__":
    samples = [
        "How do I change the theme color?",
        "Build fails after upgrade, proxy timeout while installing.",
        "App crashes with segfault when I open a large file.",
        "No data loss, but the login page is slow for all users.",
        "Outage today, all users affected.",
        "Something is odd.",
    ]
    for s in samples:
        print(s)
        print("   priority:", priority_floor(s, "P3"), "| level:", assign_level(s))
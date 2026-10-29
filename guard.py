from signals import extract_signals

# what a developer needs before an L3 ticket is worth their time, per team
REQUIRED = {
    "Auth/Network": ["error evidence", "environment", "repro steps"],
    "Database/Data Pipeline": ["error evidence", "environment", "repro steps"],
    "Deployment": ["error evidence", "environment"],
    "UI/Frontend": ["environment", "repro steps"],
}

# what we ask the reporter for, when something is missing
QUESTIONS = {
    "error evidence": "Paste the exact error message, error code, or log output.",
    "environment": "Tell us the OS, browser or runtime, and the version of the software.",
    "repro steps": "List the steps to reproduce the problem, one per line.",
}


def missing_details(text, team):
    signals = extract_signals(text)
    has = {
        "error evidence": signals["has_error_code"] or signals["has_logs"] or signals["has_stack_trace"],
        "environment": signals["has_environment"],
        "repro steps": signals["has_repro_steps"],
    }
    needed = REQUIRED.get(team, ["error evidence", "environment", "repro steps"])
    return [item for item in needed if not has[item]]


def low_confidence_reasons(team_status, closest_similarity, low_similarity):
    reasons = []
    if team_status == "ambiguous":
        reasons.append("the model is torn between two or more teams")
    if team_status == "out_of_distribution":
        reasons.append("the ticket does not fit any known team")
    if closest_similarity < low_similarity:
        reasons.append("the ticket looks unlike any past ticket")
    return reasons


def run_guard(text, team, level, team_status, closest_similarity, low_similarity,
              priority="P3", priority_reason=""):
    if level not in ("L1", "L2", "L3"):
        raise ValueError("level must be L1, L2 or L3, got: " + str(level))

    unsure = low_confidence_reasons(team_status, closest_similarity, low_similarity)

    # L1 and L2: always routed, but flagged for review if we are not sure about the team
    if level != "L3":
        status = f"Routed to {level} - {team}"
        if unsure:
            status += " (low confidence, please review)"
        return {"status": status, "missing": [], "reasons": unsure, "checklist": []}

    # L3: check that the developer has something to work with
    missing = missing_details(text, team)
    reasons = list(unsure)
    if missing:
        reasons.insert(0, "missing details: " + ", ".join(missing))

    if not reasons:
        return {"status": f"Routed to L3 - {team}", "missing": [], "reasons": [], "checklist": []}

    checklist = [QUESTIONS[item] for item in missing]
    if unsure:
        checklist.append("Describe which part of the product is affected, so we can pick the right team.")

    # a P1 from an explicit floor rule must not wait for missing details: route now, ask in parallel
    if priority == "P1" and priority_reason.startswith("floor rule"):
        status = f"Routed to L3 - {team} (P1 escalation, details requested)"
    else:
        status = "Needs Clarification"

    return {"status": status, "missing": missing, "reasons": reasons, "checklist": checklist}


if __name__ == "__main__":
    good = "Login fails with invalid_grant on staging, Chrome 126 on Windows 11.\nSteps to reproduce:\n1. open the app\n2. click sign in\n3. see the error page"
    vague = "The app crashes sometimes, please fix."

    print(run_guard(good, "Auth/Network", "L3", "confident", 0.80, 0.67))
    print(run_guard(vague, "Auth/Network", "L3", "ambiguous", 0.60, 0.67))
    print(run_guard(vague, "Auth/Network", "L3", "ambiguous", 0.60, 0.67, "P1", "floor rule: 'outage'"))
    print(run_guard(vague, "Auth/Network", "L2", "ambiguous", 0.80, 0.67))
    print(run_guard(vague, "Auth/Network", "L2", "confident", 0.80, 0.67))
    print(run_guard(vague, "Auth/Network", "L3", "ambiguous", 0.60, 0.67, "P1", "model prediction")["status"])
# [Intelligent-Support-Ticket-Triage-Missing-Info-Detector](https://github.com/GowthamSenthilKumarGSK/Intelligent-Support-Ticket-Triage-Missing-Info-Detector)

**Track:** AI / NLP and Smart Routing

A local Python app that reads a support ticket and decides:

- **Team** that should get it: Auth/Network, Database/Data Pipeline, Deployment or UI/Frontend
- **Priority:** P1, P2 or P3
- **Level:** L1, L2 or L3 (how deep the technical work is)
- **Whether it can be routed now**, or whether the reporter must first send more information (the **Information Gap and Misrouting Guard**)

---

## Architecture (5 bullets)

- **Frozen embedder plus small classifiers.** `bge-base-en-v1.5` turns each ticket into a vector and two logistic-regression heads predict **team** and **priority**. *Why:* with about 900 labelled tickets this is more reliable than fine-tuning a large model, and it trains in seconds on a laptop.

- **Calibrated confidence.** A **conformal prediction set** says how many teams are plausible, and a **nearest-neighbour check** says whether the ticket resembles any past one. *Why:* a wrong confident answer is worse than "not sure", and the thresholds come from data, not guesses.

- **Priority and level are decided separately.** Priority is the model plus a **safety floor** of explicit phrases (outage, data loss, breach) that force P1; level (L1/L2/L3) comes from **readable rules**. *Why:* urgency and technical depth are different questions, and a production outage can be P1 yet an L2 job.

- **Information Gap and Misrouting Guard.** For L3 tickets it checks the team-specific details a developer needs (**error evidence, environment, repro steps**). If any are missing or the team is uncertain, it returns `Needs Clarification` with a checklist; a floor-rule P1 is routed immediately while details are requested. *Why:* it stops developers receiving tickets they cannot act on, without delaying urgent ones.

- **Every decision is explained.** The app shows which rule fired, what is missing, and the most similar past tickets. *Why:* the rules sit in short lists in `rules.py` and `guard.py`, so a reviewer can see exactly what drives each result.

---

## Screenshots

### Normal cases

**Good L3 ticket** (all details present, routed to L3)

![Good L3 ticket](screenshots/01_good_l3.png)

**L3 ticket with missing details** (held back, checklist generated)

![L3 with missing details](screenshots/02_l3_missing.png)

**How-to question** (routed to L1, priority capped at P3)

![How-to question](screenshots/04_howto.png)

**Production outage** (P1 from the safety floor)

![Production outage](screenshots/05_outage.png)

**P1 incident with missing details** (routed immediately, details requested in parallel)

![P1 with missing details](screenshots/09_p1_missing.png)

**Command-line run**

![Command-line run](screenshots/10_cli.png)

### Edge cases

**Vague serious ticket**

![Vague serious ticket](screenshots/03_vague.png)

**Empty ticket**

![Empty ticket](screenshots/06_empty.png)

**One-word ticket**

![One word](screenshots/07_one_word.png)

**Out-of-domain ticket** (a pizza order)

![Out of domain](screenshots/08_out_of_domain.png)

---

## How to run

```
pip install -r requirements.txt
python prepare_data.py      # cleans data/tickets_clean.csv, adds signals, writes data/tickets_ready.csv
python train_model.py       # embeds tickets, trains the team and priority heads
python confidence.py        # calibrates the confidence thresholds
streamlit run app.py        # opens the interface
python triage.py            # same pipeline, in the terminal
```

---

## Data

- **Source:** the public Hugging Face dataset `sharjeelyunus/github-issues-dataset` (about 114,000 GitHub issues). We sampled and cleaned **905 tickets**.
- **Splits:** 665 train, 200 held out of training, 40 kept for the demo.
- **Labels:** team and priority are **weak labels** derived from the issues' own labels and repository rules, not hand-written support labels.
- **Detail signals** (error code, environment, repro steps, logs) are found by pattern matching in `signals.py`. We checked them against the issue-template fields on the 571 tickets that have a template:

| Signal | Agreement | Precision | Recall |
|---|---|---|---|
| Environment | 0.81 | 0.73 | 0.92 |
| Repro steps | 0.84 | 0.86 | 0.75 |
| Logs | 0.86 | 0.75 | 0.50 |

About 11% of tickets contain an error code or exception name and 7% contain a stack trace.

---

## Results

Measured by **5-fold cross-validation** on the 665 training tickets:

| Head | Accuracy | Macro F1 |
|---|---|---|
| Team | 0.863 | 0.867 |
| Priority | 0.668 | 0.641 |

On 240 tickets the model had not trained on, the conformal check found **209 confident (87%)**, 30 ambiguous and 1 out of distribution. Only 4.6% looked unlike any training ticket. These thresholds were calibrated on out-of-fold training predictions.

---

## Limitations

- **Priority is the weakest part.** The priority labels come mostly from "bug versus feature request", so P2 versus P3 is hard to separate (accuracy 0.67). P1 predictions are only 39% precise, which is why only explicit floor rules trigger immediate escalation, and why how-to questions are capped at P3.
- **Level rules are keyword-based** and can over-assign L3 when a ticket contains a word like "crash". A ticket that matches no rule gets the default L2 and is flagged "level unclear, please review".
- **Short tickets** look unlike the long training tickets, so they are often flagged for review. The out-of-domain rule fires only when a ticket also contains no technical cue and has a top team probability under 0.5. That 0.5 cut-off was chosen by hand, not learned from data.
- **"Confident"** means the conformal set holds exactly one team. The probability shown is the model's top score, and it can be modest even when the answer is confident.
- **Environment detection** misses some tickets that describe their setup in plain prose.
- **Calibration** uses cross-validated training predictions, and the labels are weak, so the reported numbers measure agreement with those labels, not with human judgement.

---

## Files

| File | Purpose |
|---|---|
| `signals.py` | finds error codes, environment, repro steps and logs in a ticket |
| `check_signals.py` | compares those signals with the issue-template fields |
| `prepare_data.py` | cleans the data and adds the signal columns |
| `train_model.py` | embeds tickets and trains the team and priority heads |
| `confidence.py` | conformal and nearest-neighbour confidence |
| `rules.py` | priority safety floor and level rules |
| `guard.py` | the Information Gap and Misrouting Guard |
| `triage.py` | the full pipeline for one ticket |
| `app.py` | Streamlit interface |

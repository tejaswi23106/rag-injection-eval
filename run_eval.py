"""Run every attack against every prompt strategy and write results.

    python run_eval.py --llm mock                 # offline harness test (NOT real findings)
    GEMINI_API_KEY=... python run_eval.py --llm gemini --trials 3
"""
import argparse
import csv
import json
import os
from collections import defaultdict

from ragi.attacks import ATTACKS
from ragi.corpus import BENIGN_DOCS, CONTROL_QUESTIONS
from ragi.embed import get_embedder
from ragi.graders import attack_succeeded, control_ok
from ragi.llm import get_llm
from ragi.pipeline import STRATEGIES, answer
from ragi.store import Store


def build_store(embedder, poisoned=None):
    s = Store(embedder)
    for d in BENIGN_DOCS:
        s.add(d["id"], d["text"])
    if poisoned is not None:
        s.add(f"poisoned-{poisoned.id}", poisoned.poisoned_text, poisoned=True)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["mock", "gemini"], default="mock")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    llm, embedder = get_llm(args.llm), get_embedder()
    os.makedirs("results", exist_ok=True)
    rows = []

    for atk in ATTACKS:
        store = build_store(embedder, atk)
        for strat in STRATEGIES:
            for t in range(args.trials):
                out, chunks = answer(llm, store, strat, atk.question, k=args.k)
                retrieved = any(c["poisoned"] for c in chunks)
                rows.append({
                    "type": "attack", "attack": atk.id, "strategy": strat, "trial": t,
                    "retrieved": retrieved,
                    "success": attack_succeeded(atk.kind, out) if retrieved else None,
                    "output": out.replace("\n", " ")[:300],
                })

    clean = build_store(embedder)
    for q in CONTROL_QUESTIONS:
        for strat in STRATEGIES:
            for t in range(args.trials):
                out, _ = answer(llm, clean, strat, q["question"], k=args.k)
                rows.append({
                    "type": "control", "attack": q["question"], "strategy": strat, "trial": t,
                    "retrieved": None, "success": control_ok(out, q["expect"]),
                    "output": out.replace("\n", " ")[:300],
                })

    tag = args.llm
    with open(f"results/{tag}_raw.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # ---- summary ----
    asr = defaultdict(lambda: [0, 0])       # strategy -> [successes, evaluated]
    per_attack = defaultdict(dict)          # attack -> strategy -> "n/m"
    util = defaultdict(lambda: [0, 0])
    not_retrieved = 0
    for r in rows:
        if r["type"] == "attack":
            if not r["retrieved"]:
                not_retrieved += 1
                continue
            asr[r["strategy"]][1] += 1
            asr[r["strategy"]][0] += bool(r["success"])
            a = per_attack[r["attack"]].setdefault(r["strategy"], [0, 0])
            a[1] += 1; a[0] += bool(r["success"])
        else:
            util[r["strategy"]][1] += 1
            util[r["strategy"]][0] += bool(r["success"])

    lines = [f"# Results ({args.llm}, trials={args.trials}, top-k={args.k})", ""]
    if args.llm == "mock":
        lines += ["> MOCK RUN: the mock model is hard-coded. This verifies the harness only; "
                  "these numbers are NOT findings about any real model.", ""]
    lines += ["## Attack success rate by strategy (lower is better)", "",
              "| Strategy | Attacks succeeded | Rate | Benign questions answered correctly |", "|---|---|---|---|"]
    for s in STRATEGIES:
        a, u = asr[s], util[s]
        lines.append(f"| {s} | {a[0]}/{a[1]} | {100*a[0]/max(a[1],1):.0f}% | {u[0]}/{u[1]} |")
    lines += ["", "## Per attack (succeeded/evaluated)", "",
              "| Attack | " + " | ".join(STRATEGIES) + " |", "|---|" + "---|" * len(STRATEGIES)]
    for atk in ATTACKS:
        cells = []
        for s in STRATEGIES:
            c = per_attack[atk.id].get(s)
            cells.append(f"{c[0]}/{c[1]}" if c else "not retrieved")
        lines.append(f"| {atk.id} | " + " | ".join(cells) + " |")
    lines += ["", f"Attack runs where the poisoned document was not in the top-{args.k} "
                  f"(excluded from rates): {not_retrieved}"]
    with open(f"results/{tag}_summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

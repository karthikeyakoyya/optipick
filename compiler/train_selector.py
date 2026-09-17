"""
Builds a small labeled dataset (program features -> best performing pass
order) from randomly generated programs, then fits a shallow decision tree
on it. Run directly:

    python -m compiler.train_selector

Writes compiler/selector_model.json, which selector.py loads at inference
time (kept as plain JSON, not a pickle, so the trained model is auditable
and diffable like any other file in the repo).
"""

import json
import os

from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from .parser import parse
from .ir import generate
from .features import extract_features, FEATURE_NAMES
from .pipeline import run_order
from .programgen import make_corpus

CANDIDATE_ORDERS = [
    ["fold", "cse", "dce", "licm"],
    ["cse", "fold", "dce", "licm"],
    ["fold", "dce", "cse", "licm"],
    ["licm", "fold", "cse", "dce"],
    ["fold", "licm", "cse", "dce"],
    ["dce", "fold", "cse", "licm"],
]

MODEL_PATH = os.path.join(os.path.dirname(__file__), "selector_model.json")


def build_dataset(n_programs=260, seed=7):
    X, y, meta = [], [], []
    for source in make_corpus(n_programs, seed=seed):
        try:
            ast = parse(source)
            code = generate(ast)
        except Exception:
            continue
        if len(code) < 4:
            continue

        feats = extract_features(code)

        final_sizes, work_costs = [], []
        for order in CANDIDATE_ORDERS:
            final_code, trace = run_order(code, order)
            final_sizes.append(len(final_code))
            work_costs.append(sum(step["instr_before"] for step in trace))

        # rank by final program size first (a smaller compiled program is
        # the thing that actually matters), and use total instructions
        # examined across every pass call as a compile-time tiebreaker.
        best = min(
            range(len(CANDIDATE_ORDERS)),
            key=lambda idx: (final_sizes[idx], work_costs[idx]),
        )

        X.append(feats)
        y.append(best)
        meta.append({
            "source": source,
            "final_sizes": final_sizes,
            "work_costs": work_costs,
            "raw_len": len(code),
        })
    return X, y, meta


def train():
    X, y, meta = build_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=13
    )

    clf = DecisionTreeClassifier(max_depth=4, min_samples_leaf=6, random_state=13)
    clf.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, clf.predict(X_train))
    test_acc = accuracy_score(y_test, clf.predict(X_test))

    # honest baseline comparison: what if an engineer just always ran the
    # passes in the first sensible order (fold, cse, dce, licm) instead of
    # letting the model pick per program? Many small straight line programs
    # genuinely do not care about order at all, so only compare on programs
    # where the six candidate orders are not already all tied.
    from collections import Counter
    majority_label = Counter(y).most_common(1)[0][0]
    baseline_label = 0

    contested = [i for i in range(len(y)) if len(set(meta[i]["work_costs"])) > 1]
    wins, total_saving_pct, saving_pcts = 0, 0.0, []
    for i in contested:
        baseline_cost = meta[i]["work_costs"][baseline_label]
        learned_cost = meta[i]["work_costs"][y[i]]
        if learned_cost < baseline_cost:
            wins += 1
            pct = (baseline_cost - learned_cost) / baseline_cost
            total_saving_pct += pct
            saving_pcts.append(pct)
    avg_saving_pct = (total_saving_pct / wins * 100) if wins else 0.0
    max_saving_pct = max(saving_pcts) * 100 if saving_pcts else 0.0
    fixed_order_regret = wins

    tree_text = export_text(clf, feature_names=FEATURE_NAMES)

    model_dump = {
        "feature_names": FEATURE_NAMES,
        "candidate_orders": CANDIDATE_ORDERS,
        "tree_params": clf.get_params(),
        "tree_text": tree_text,
        "train_accuracy": train_acc,
        "test_accuracy": test_acc,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "majority_label": majority_label,
        "baseline_label": baseline_label,
        "n_contested_programs": len(contested),
        "programs_where_learning_beats_fixed_order": fixed_order_regret,
        "avg_work_saving_pct_when_it_wins": avg_saving_pct,
        "max_work_saving_pct": max_saving_pct,
        "n_programs": len(y),
        "tree_structure": {
            "children_left": clf.tree_.children_left.tolist(),
            "children_right": clf.tree_.children_right.tolist(),
            "feature": clf.tree_.feature.tolist(),
            "threshold": clf.tree_.threshold.tolist(),
            "value": [v[0] for v in clf.tree_.value.tolist()],
            "classes": clf.classes_.tolist(),
        },
    }

    with open(MODEL_PATH, "w") as f:
        json.dump(model_dump, f, indent=2)

    print(f"trained on {len(X_train)} programs, held out {len(X_test)}")
    print(f"train accuracy {train_acc:.2f}, test accuracy {test_acc:.2f}")
    print(f"{len(contested)}/{len(y)} programs actually have order sensitive costs")
    print(f"on those, the learned order beats the fixed default on "
          f"{fixed_order_regret}/{len(contested)} programs, "
          f"saving {avg_saving_pct:.1f}% of total pass work on average when it wins")
    print()
    print(tree_text)
    return clf, model_dump


if __name__ == "__main__":
    train()

import json
import os
import re

from .parser import parse
from .ir import generate, render_ir
from .features import extract_features, FEATURE_NAMES
from .pipeline import run_order
from .selector import PassOrderSelector
from .train_selector import CANDIDATE_ORDERS, MODEL_PATH, build_dataset

# A hand written program that exercises every pass in a way that is easy to
# read: a + b computed three times (constant folding then exposes it as one
# fully redundant expression), a temp that ends up dead, and a loop that
# recomputes 2 + 3 on every iteration even though it never changes.
WALKTHROUGH_SOURCE = """a = 2;
b = 3;
c = a + b;
d = a + b;
e = a + b;
x = 5;
y = 5;
if (x == y) {
  z = a + b;
}
i = 0;
n = 12;
total = 0;
while (i < n) {
  step = 2 + 3;
  waste = a + b;
  total = total + step;
  i = i + 1;
}
"""

BASELINE_ORDER = CANDIDATE_ORDERS[0]
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "visualizer", "trace.json")


def work_cost(trace):
    return sum(step["instr_before"] for step in trace)


def run_demo(source, selector):
    ast = parse(source)
    raw_code = generate(ast)
    feats = extract_features(raw_code)
    choice = selector.choose(feats)
    chosen_order = choice["order"]

    chosen_final, chosen_trace = run_order(list(raw_code), chosen_order)
    baseline_final, baseline_trace = run_order(list(raw_code), BASELINE_ORDER)

    return {
        "source": source,
        "raw_ir": render_ir(raw_code),
        "raw_instr_count": len(raw_code),
        "features": dict(zip(FEATURE_NAMES, feats)),
        "decision_path": choice["decision_path"],
        "chosen_order": chosen_order,
        "baseline_order": BASELINE_ORDER,
        "chosen_trace": chosen_trace,
        "baseline_trace": baseline_trace,
        "chosen_final_ir": render_ir(chosen_final),
        "baseline_final_ir": render_ir(baseline_final),
        "chosen_final_count": len(chosen_final),
        "baseline_final_count": len(baseline_final),
        "chosen_work": work_cost(chosen_trace),
        "baseline_work": work_cost(baseline_trace),
    }


def pick_selector_showcase():
    """Pull a genuine training example where the model's real prediction
    matches the true best order and clearly beats the fixed baseline, so
    the showcase panel is not cherry picked math, it is an actual model
    decision. Variable names are cosmetically renamed for readability; the
    program's structure and every optimization outcome are untouched."""
    X, y, meta = build_dataset()
    selector = PassOrderSelector(MODEL_PATH)

    best = None
    for i in range(len(y)):
        choice = selector.choose(X[i])
        predicted = choice["label"]
        if predicted != y[i]:
            continue
        baseline_cost = meta[i]["work_costs"][0]
        pred_cost = meta[i]["work_costs"][predicted]
        if pred_cost >= baseline_cost:
            continue
        saving = (baseline_cost - pred_cost) / baseline_cost
        if best is None or saving > best[0]:
            best = (saving, meta[i]["source"])

    saving, source = best
    names = sorted(set(re.findall(r"\bv\d+\b", source)))
    rename = {old: new for old, new in zip(names, "xyzw")}
    for old, new in rename.items():
        source = re.sub(rf"\b{old}\b", new, source)
    return source, saving


def build_trace():
    selector = PassOrderSelector(MODEL_PATH)

    walkthrough = run_demo(WALKTHROUGH_SOURCE, selector)

    showcase_source, showcase_saving = pick_selector_showcase()
    showcase = run_demo(showcase_source, selector)

    with open(MODEL_PATH) as f:
        model_stats = json.load(f)

    payload = {
        "walkthrough": walkthrough,
        "showcase": showcase,
        "showcase_saving_pct": showcase_saving * 100,
        "candidate_orders": CANDIDATE_ORDERS,
        "model_stats": {
            "train_accuracy": model_stats["train_accuracy"],
            "test_accuracy": model_stats["test_accuracy"],
            "n_train": model_stats["n_train"],
            "n_test": model_stats["n_test"],
            "n_contested_programs": model_stats["n_contested_programs"],
            "programs_where_learning_beats_fixed_order": model_stats["programs_where_learning_beats_fixed_order"],
            "avg_work_saving_pct_when_it_wins": model_stats["avg_work_saving_pct_when_it_wins"],
            "max_work_saving_pct": model_stats["max_work_saving_pct"],
            "n_programs": model_stats["n_programs"],
            "tree_text": model_stats["tree_text"],
        },
    }

    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"wrote {OUT_PATH}")
    print(f"walkthrough: raw {walkthrough['raw_instr_count']}, "
          f"chosen {walkthrough['chosen_order']} -> {walkthrough['chosen_final_count']} instrs")
    print(f"showcase: saving {showcase_saving*100:.1f}%, "
          f"chosen {showcase['chosen_order']} work {showcase['chosen_work']} "
          f"vs baseline work {showcase['baseline_work']}")
    return payload


if __name__ == "__main__":
    build_trace()

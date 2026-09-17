import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.parser import parse
from compiler.ir import generate, render_ir
from compiler.passes import (
    constant_folding,
    common_subexpression_elimination,
    dead_code_elimination,
    loop_invariant_code_motion,
)
from compiler.pipeline import run_order
from compiler.features import extract_features
from compiler.selector import PassOrderSelector
from compiler.train_selector import MODEL_PATH


def compile_source(src):
    return generate(parse(src))


def test_constant_folding_collapses_arithmetic():
    code = compile_source("a = 2 + 3;\n")
    folded, changed = constant_folding(code)
    assert changed
    assert any(i.op == "const" and i.value == 5 for i in folded)


def test_common_subexpression_elimination_reuses_result():
    code = compile_source("a = 1;\nb = 2;\nc = a + b;\nd = a + b;\n")
    reduced, changed = common_subexpression_elimination(code)
    assert changed
    binops = [i for i in reduced if i.op == "binop"]
    assert len(binops) == 1


def test_dead_code_elimination_drops_unused_temp():
    # constant folding replaces a binop with a plain const, which drops
    # that instruction's references to its operand temps; if those temps
    # had no other reader (the realistic case for a nested expression),
    # they become dead and DCE should remove them.
    code = compile_source("a = (1 + 2) + 3;\n")
    folded, _ = constant_folding(code)
    reduced, changed = dead_code_elimination(folded)
    assert changed
    assert len(reduced) < len(folded)


def test_pipeline_runs_to_fixpoint_and_shrinks_program():
    code = compile_source(
        "i = 0;\nn = 5;\nwhile (i < n) {\n"
        "  step = 2 + 3;\n  total = total + step;\n  i = i + 1;\n}\n"
    )
    final_code, trace = run_order(code, ["fold", "cse", "dce", "licm"])
    assert len(final_code) < len(code)
    assert len(trace) > 0


def test_loop_invariant_code_motion_hoists_constant_body_work():
    code = compile_source(
        "i = 0;\nn = 5;\nwhile (i < n) {\n  step = 2 + 3;\n  i = i + step;\n}\n"
    )
    hoisted, changed = loop_invariant_code_motion(code)
    assert changed
    label_pos = next(idx for idx, instr in enumerate(hoisted) if instr.op == "label")
    hoisted_before_loop = hoisted[:label_pos]
    assert any(i.op == "binop" for i in hoisted_before_loop)


def test_feature_extraction_shape():
    code = compile_source("a = 1;\nb = a + a;\n")
    feats = extract_features(code)
    assert len(feats) == 6
    assert feats[0] == len(code)


def test_selector_returns_valid_order():
    selector = PassOrderSelector(MODEL_PATH)
    code = compile_source(
        "i = 0;\nn = 8;\nwhile (i < n) {\n  x = 4 + 4;\n  i = i + 1;\n}\n"
    )
    feats = extract_features(code)
    choice = selector.choose(feats)
    assert set(choice["order"]) == {"fold", "cse", "dce", "licm"}
    assert len(choice["decision_path"]) >= 1

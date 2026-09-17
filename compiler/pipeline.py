from .ir import render_ir
from .passes import PASS_TABLE


def run_order(code, order, max_rounds=4):
    """Apply the passes in `order` repeatedly until a full round makes no
    change or max_rounds is hit. Returns the final code and a step by step
    trace suitable for driving the visualizer."""
    trace = []
    for round_no in range(max_rounds):
        round_changed = False
        for pass_name in order:
            before = len(code)
            code, changed = PASS_TABLE[pass_name](code)
            after = len(code)
            trace.append({
                "round": round_no + 1,
                "pass": pass_name,
                "changed": changed,
                "instr_before": before,
                "instr_after": after,
                "ir_after": render_ir(code),
            })
            round_changed = round_changed or changed
        if not round_changed:
            break
    return code, trace


def instr_count_after(code, order, max_rounds=4):
    final_code, _ = run_order(code, order, max_rounds)
    return len(final_code)

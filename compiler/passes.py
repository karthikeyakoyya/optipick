"""
Four optimization passes, each a pure function: (code) -> (new_code, changed).

These are simplified relative to a production compiler (no dominance tree,
no full control flow graph) but they are real, working implementations that
operate correctly over the label / goto / if_false shape the IR builder
produces, and each one is independently testable.
"""

OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b != 0 else None,
    "<": lambda a, b: 1 if a < b else 0,
    ">": lambda a, b: 1 if a > b else 0,
    "<=": lambda a, b: 1 if a <= b else 0,
    ">=": lambda a, b: 1 if a >= b else 0,
    "==": lambda a, b: 1 if a == b else 0,
}


def _is_temp(name):
    return isinstance(name, str) and name.startswith("t") and name[1:].isdigit()


def constant_folding(code):
    """Fold binops with two known constant operands, and propagate copies of
    known constants forward. Cleared at every label since we don't build a
    real control flow graph, so this stays correct across joins."""
    new_code = []
    known = {}
    changed = False

    for instr in code:
        if instr.op == "label":
            known = {}
            new_code.append(instr)
            continue

        if instr.op == "const":
            known[instr.dest] = instr.value
            new_code.append(instr)
            continue

        if instr.op == "copy":
            if instr.a in known:
                known[instr.dest] = known[instr.a]
            else:
                known.pop(instr.dest, None)
            new_code.append(instr)
            continue

        if instr.op == "binop":
            if instr.a in known and instr.b in known:
                fn = OPS[instr.value]
                result = fn(known[instr.a], known[instr.b])
                if result is not None:
                    from .ir import Instr
                    new_code.append(Instr("const", dest=instr.dest, value=result))
                    known[instr.dest] = result
                    changed = True
                    continue
            known.pop(instr.dest, None)
            new_code.append(instr)
            continue

        new_code.append(instr)

    return new_code, changed


def common_subexpression_elimination(code):
    """Replace a binop with a copy when an earlier, still valid instruction
    already computed the exact same operation on the exact same operands."""
    from .ir import Instr

    new_code = []
    available = {}  # (op, a, b) -> temp holding the result
    changed = False

    def invalidate(name):
        for key in [k for k in available if name in (k[1], k[2])]:
            del available[key]

    for instr in code:
        if instr.op == "label":
            available = {}
            new_code.append(instr)
            continue

        if instr.op == "binop":
            key = (instr.value, instr.a, instr.b)
            if key in available:
                new_code.append(Instr("copy", dest=instr.dest, a=available[key]))
                changed = True
                continue
            available[key] = instr.dest
            new_code.append(instr)
            continue

        if instr.op in ("const", "copy"):
            invalidate(instr.dest)
            new_code.append(instr)
            continue

        new_code.append(instr)

    return new_code, changed


def dead_code_elimination(code):
    """Drop instructions whose result (a compiler generated temp) is never
    read anywhere in the program. Named program variables are always kept:
    with no explicit output statement in this language, a plain variable is
    the closest thing we have to an observable result."""
    changed = True
    any_change = False
    while changed:
        changed = False
        used = set()
        for instr in code:
            for operand in (instr.a, instr.b):
                if operand is not None:
                    used.add(operand)
        survivors = []
        for instr in code:
            is_temp_def = instr.op in ("const", "copy", "binop") and _is_temp(instr.dest)
            if is_temp_def and instr.dest not in used:
                changed = True
                any_change = True
                continue
            survivors.append(instr)
        code = survivors
    return code, any_change


def _find_loop_regions(code):
    """Return a list of (label_index, goto_index) pairs, one per while loop:
    a label whose name is later targeted by a goto that appears after it."""
    label_index = {}
    regions = []
    for i, instr in enumerate(code):
        if instr.op == "label":
            label_index[instr.label] = i
        elif instr.op == "goto" and instr.label in label_index:
            regions.append((label_index[instr.label], i))
    return regions


def loop_invariant_code_motion(code):
    """Find while loop bodies (a label whose name is the target of a later
    goto) and hoist const/binop instructions whose operands are never
    written inside that body, so they run once instead of every iteration."""
    code = list(code)
    changed = False

    while True:
        regions = _find_loop_regions(code)
        if not regions:
            break

        start, end = regions[0]
        body = code[start + 1:end]

        written_vars = {
            instr.dest for instr in body
            if instr.op in ("const", "copy", "binop") and not _is_temp(instr.dest)
        }

        hoisted, kept = [], []
        for instr in body:
            if instr.op in ("const", "binop"):
                operands = [op for op in (instr.a, instr.b) if op is not None]
                if all(op not in written_vars for op in operands):
                    hoisted.append(instr)
                    continue
            kept.append(instr)

        if not hoisted:
            # nothing to hoist in this loop; move past it and keep scanning
            # the remainder of the program for other loops.
            tail_code, tail_changed = loop_invariant_code_motion(code[end + 1:])
            return code[:end + 1] + tail_code, changed or tail_changed

        changed = True
        code = code[:start] + hoisted + [code[start]] + kept + code[end:]

    return code, changed


PASS_TABLE = {
    "fold": constant_folding,
    "cse": common_subexpression_elimination,
    "dce": dead_code_elimination,
    "licm": loop_invariant_code_motion,
}

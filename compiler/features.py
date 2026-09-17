from .passes import _is_temp

FEATURE_NAMES = [
    "n_instr",
    "frac_const",
    "frac_duplicate_binop",
    "frac_unused_temp",
    "has_loop",
    "n_labels",
]


def extract_features(code):
    n_instr = len(code)
    if n_instr == 0:
        return [0, 0, 0, 0, 0, 0]

    n_const = sum(1 for i in code if i.op == "const")

    seen = set()
    duplicates = 0
    for i in code:
        if i.op != "binop":
            continue
        key = (i.value, i.a, i.b)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)

    used = set()
    for i in code:
        for operand in (i.a, i.b):
            if operand is not None:
                used.add(operand)
    unused_temps = sum(
        1 for i in code
        if i.op in ("const", "copy", "binop") and _is_temp(i.dest) and i.dest not in used
    )

    labels = [i.label for i in code if i.op == "label"]
    gotos = {i.label for i in code if i.op == "goto"}
    has_loop = 1 if any(l in gotos for l in labels) else 0

    return [
        n_instr,
        n_const / n_instr,
        duplicates / n_instr,
        unused_temps / n_instr,
        has_loop,
        len(labels),
    ]

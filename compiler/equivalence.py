"""
Every netlist pass claims to preserve behavior; this checks that claim by
simulation instead of assuming it. Exhaustive for small input counts,
random sampling once the input space is too large to enumerate.
"""

import random

from .netlist_sim import simulate, all_input_vectors

EXHAUSTIVE_LIMIT = 16  # 2**16 vectors is still fast to simulate in Python
RANDOM_SAMPLES = 500


def check_equivalence(original, optimized, seed=0):
    if set(original.inputs) != set(optimized.inputs):
        return False, "input ports differ", 0
    if set(original.outputs) != set(optimized.outputs):
        return False, "output ports differ", 0

    n = len(original.inputs)
    if n <= EXHAUSTIVE_LIMIT:
        vectors = list(all_input_vectors(original))
        mode = "exhaustive"
    else:
        rng = random.Random(seed)
        vectors = [
            {name: rng.randint(0, 1) for name in original.inputs}
            for _ in range(RANDOM_SAMPLES)
        ]
        mode = "random sample"

    for vec in vectors:
        orig_vals = simulate(original, vec)
        opt_vals = simulate(optimized, vec)
        for out in original.outputs:
            if orig_vals[out] != opt_vals[out]:
                return False, f"mismatch on {out} for input {vec}", len(vectors)

    return True, mode, len(vectors)

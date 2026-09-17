"""
Three optimization passes over a gate level Netlist, structurally the same
ideas as passes.py applies to program IR, applied to a circuit graph
instead: reuse an identical computation instead of repeating it, drop
anything nothing reads, and fold away logic whose inputs are already known
constants.
"""

from .netlist import Gate


def _rewire(nl, old_wire, new_wire):
    """Replace every reference to old_wire with new_wire, in every gate's
    inputs and in the primary output list, then drop old_wire from the
    wire declaration list if it is no longer driven by anything else."""
    for g in nl.gates:
        g.inputs = [new_wire if w == old_wire else w for w in g.inputs]
    nl.outputs = [new_wire if w == old_wire else w for w in nl.outputs]


def redundant_gate_elimination(nl):
    """If two gates compute the exact same function of the exact same
    inputs, keep the first and rewire every consumer of the second gate's
    output onto the first gate's output, then drop the second gate."""
    nl = nl.copy()
    seen = {}
    survivors = []
    changed = False

    for g in nl.gates:
        if g.kind in ("tie0", "tie1"):
            survivors.append(g)
            continue
        sig = g.signature()
        if sig in seen:
            _rewire(nl, g.output, seen[sig])
            changed = True
            continue
        seen[sig] = g.output
        survivors.append(g)

    nl.gates = survivors
    return nl, changed


def dead_gate_elimination(nl):
    """Drop any gate whose output wire is never used, iterating to a fixed
    point since removing one dead gate can expose another one behind it."""
    nl = nl.copy()
    changed_ever = False

    while True:
        used = set(nl.outputs)
        for g in nl.gates:
            used.update(g.inputs)

        survivors = [g for g in nl.gates if g.output in used]
        if len(survivors) == len(nl.gates):
            break
        changed_ever = True
        nl.gates = survivors

    return nl, changed_ever


def constant_propagation(nl):
    """Fold gates whose inputs are already known constants: an AND/NAND
    with any 0 input, an OR/NOR with any 1 input, and any gate whose every
    input is constant, all collapse to a tie cell instead of a real gate."""
    nl = nl.copy()
    const = {}
    changed = False

    survivors = []
    for g in nl.gates:
        if g.kind == "tie0":
            const[g.output] = 0
            survivors.append(g)
            continue
        if g.kind == "tie1":
            const[g.output] = 1
            survivors.append(g)
            continue

        in_const = [const.get(w) for w in g.inputs]

        folded = None
        if g.kind in ("and", "nand") and 0 in in_const:
            folded = 1 if g.kind == "nand" else 0
        elif g.kind in ("or", "nor") and 1 in in_const:
            folded = 0 if g.kind == "nor" else 1
        elif all(v is not None for v in in_const):
            from .netlist_sim import GATE_FN
            folded = GATE_FN[g.kind](in_const)

        if folded is not None:
            const[g.output] = folded
            survivors.append(Gate("tie1" if folded else "tie0", g.name, g.output))
            changed = True
        else:
            survivors.append(g)

    nl.gates = survivors
    return nl, changed


def prune_unused_wire_declarations(nl):
    """Cosmetic pass: drop wire declarations no gate or output still
    references, so a fully optimized netlist doesn't list dead wire names."""
    nl = nl.copy()
    referenced = set(nl.outputs)
    for g in nl.gates:
        referenced.add(g.output)
        referenced.update(g.inputs)
    nl.wires = [w for w in nl.wires if w in referenced]
    return nl


NETLIST_PASS_TABLE = {
    "redundant": redundant_gate_elimination,
    "dead": dead_gate_elimination,
    "const": constant_propagation,
}


def run_netlist_order(nl, order, max_rounds=4):
    trace = []
    for round_no in range(max_rounds):
        round_changed = False
        for pass_name in order:
            before = len(nl.gates)
            nl, changed = NETLIST_PASS_TABLE[pass_name](nl)
            after = len(nl.gates)
            trace.append({
                "round": round_no + 1,
                "pass": pass_name,
                "changed": changed,
                "gates_before": before,
                "gates_after": after,
            })
            round_changed = round_changed or changed
        if not round_changed:
            break
    nl = prune_unused_wire_declarations(nl)
    return nl, trace

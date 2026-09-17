"""
A plain Python event free simulator for the combinational netlists
netlist.py parses. Given an assignment for every primary input, it
evaluates every gate in dependency order and returns the value on every
wire, including the primary outputs.

This is a simulator for verifying the netlist passes are behavior
preserving, not a timing accurate hardware simulator: gates are evaluated
once each in topological order, with no propagation delay modeled.
"""

GATE_FN = {
    "and":  lambda vals: int(all(vals)),
    "or":   lambda vals: int(any(vals)),
    "nand": lambda vals: int(not all(vals)),
    "nor":  lambda vals: int(not any(vals)),
    "xor":  lambda vals: int(sum(vals) % 2 == 1),
    "xnor": lambda vals: int(sum(vals) % 2 == 0),
    "not":  lambda vals: int(not vals[0]),
    "buf":  lambda vals: int(vals[0]),
}


class SimulationError(Exception):
    pass


def _topo_order(nl):
    """Order gates so every gate is evaluated after every gate that feeds
    it. Raises if the netlist has a combinational cycle, since this
    simulator only supports acyclic (purely combinational) circuits."""
    driver_of = {}
    for g in nl.gates:
        driver_of[g.output] = g

    visited, visiting, order = set(), set(), []

    def visit(gate):
        if gate.name in visited:
            return
        if gate.name in visiting:
            raise SimulationError(f"combinational cycle through gate {gate.name}")
        visiting.add(gate.name)
        for inp in gate.inputs:
            if inp in driver_of:
                visit(driver_of[inp])
        visiting.discard(gate.name)
        visited.add(gate.name)
        order.append(gate)

    for g in nl.gates:
        visit(g)
    return order


def simulate(nl, input_values: dict) -> dict:
    """input_values maps every primary input name to 0 or 1. Returns a dict
    of every wire (inputs, internal wires, outputs) to its simulated 0/1
    value."""
    missing = set(nl.inputs) - set(input_values)
    if missing:
        raise SimulationError(f"missing input values for {sorted(missing)}")

    values = dict(input_values)

    for gate in _topo_order(nl):
        if gate.kind == "tie0":
            values[gate.output] = 0
            continue
        if gate.kind == "tie1":
            values[gate.output] = 1
            continue
        in_vals = [values[w] for w in gate.inputs]
        values[gate.output] = GATE_FN[gate.kind](in_vals)

    return values


def all_input_vectors(nl):
    """Every possible 0/1 assignment for the primary inputs. Only sensible
    for small input counts; exhaustive equivalence checking below falls
    back to random sampling once the input count gets large."""
    n = len(nl.inputs)
    for i in range(2 ** n):
        yield {name: (i >> idx) & 1 for idx, name in enumerate(nl.inputs)}

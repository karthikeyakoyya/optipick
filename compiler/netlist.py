"""
Parser for a deliberately small, structural subset of Verilog: a module
header with single-bit input/output ports, wire declarations, and gate
instantiations of built in primitives (and, or, not, xor, nand, nor, buf,
xnor), plus two pseudo primitives, tie0 and tie1, for constant sources.

This is not a general Verilog parser. It reads exactly the shape a gate
level netlist takes after synthesis has already broken a design down to
primitive gates, which is the representation OptiPick's netlist passes
operate on. Behavioral constructs (always blocks, if/case, multi-bit buses)
are out of scope on purpose, the same way the compiler side only handles a
small toy language rather than a general purpose one.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict

GATE_TYPES = {"and", "or", "not", "xor", "nand", "nor", "buf", "xnor"}
TIE_TYPES = {"tie0", "tie1"}


@dataclass
class Gate:
    kind: str          # one of GATE_TYPES or TIE_TYPES
    name: str          # instance name, e.g. "g3"
    output: str        # wire name this gate drives
    inputs: List[str] = field(default_factory=list)

    def signature(self):
        """A commutative gate's behavior does not depend on input order,
        so two gates of the same kind over the same input set (regardless
        of order) compute the same value and are candidates for merging."""
        if self.kind in ("and", "or", "xor", "nand", "nor", "xnor"):
            return (self.kind, tuple(sorted(self.inputs)))
        return (self.kind, tuple(self.inputs))


@dataclass
class Netlist:
    name: str
    inputs: List[str]
    outputs: List[str]
    wires: List[str]
    gates: List[Gate]

    def all_signals(self):
        return set(self.inputs) | set(self.outputs) | set(self.wires)

    def copy(self):
        return Netlist(
            self.name,
            list(self.inputs),
            list(self.outputs),
            list(self.wires),
            [Gate(g.kind, g.name, g.output, list(g.inputs)) for g in self.gates],
        )


PORT_RE = re.compile(r"module\s+(\w+)\s*\(([^)]*)\)\s*;", re.S)
WIRE_RE = re.compile(r"\bwire\s+([^;]+);")
GATE_RE = re.compile(
    r"\b(" + "|".join(GATE_TYPES | TIE_TYPES) + r")\s+(\w+)\s*\(([^)]*)\)\s*;"
)


def parse_netlist(source: str) -> Netlist:
    header = PORT_RE.search(source)
    if not header:
        raise ValueError("no module header found")
    name = header.group(1)

    inputs, outputs = [], []
    for port in header.group(2).split(","):
        port = port.strip()
        if not port:
            continue
        if port.startswith("input"):
            inputs.append(port.replace("input", "").strip())
        elif port.startswith("output"):
            outputs.append(port.replace("output", "").strip())
        else:
            raise ValueError(f"unrecognized port declaration: {port!r}")

    wires = []
    for m in WIRE_RE.finditer(source):
        wires.extend(w.strip() for w in m.group(1).split(",") if w.strip())

    gates = []
    for m in GATE_RE.finditer(source):
        kind, inst_name, args = m.group(1), m.group(2), m.group(3)
        arg_list = [a.strip() for a in args.split(",") if a.strip()]
        if kind in TIE_TYPES:
            output, gate_inputs = arg_list[0], []
        else:
            output, gate_inputs = arg_list[0], arg_list[1:]
        gates.append(Gate(kind, inst_name, output, gate_inputs))

    return Netlist(name, inputs, outputs, wires, gates)


def render_netlist(nl: Netlist) -> str:
    lines = [f"module {nl.name}("]
    lines.append("  " + ", ".join(
        [f"input {p}" for p in nl.inputs] + [f"output {p}" for p in nl.outputs]
    ) + ");")
    if nl.wires:
        lines.append(f"  wire {', '.join(nl.wires)};")
    for g in nl.gates:
        args = ", ".join([g.output] + g.inputs)
        lines.append(f"  {g.kind} {g.name}({args});")
    lines.append("endmodule")
    return "\n".join(lines)

"""
A second front end for the same netlist optimizer: a deliberately small
structural VHDL subset, entity/port declaration plus an architecture body
that instantiates primitive gate components with named port maps, parsed
into the exact same Netlist/Gate objects netlist.py produces from Verilog.

Because the simulator, the three optimization passes, and the equivalence
checker all operate on that shared Netlist representation rather than on
source text, none of them needed to change to support a second input
language. Only a parser (this file) and a printer (render_vhdl) are new.

VHDL primitive components map onto the same gate kinds as the Verilog
side: and2, or2, xor2, nand2, nor2, xnor2 (two input), not1/buf1 (one
input), and tie0/tie1 for constant sources. This is not general VHDL,
the same way netlist.py is not general Verilog: no generics, no
processes, no multi-bit signals.
"""

import re
from .netlist import Netlist, Gate

COMPONENT_TO_GATE = {
    "and2": "and", "or2": "or", "xor2": "xor",
    "nand2": "nand", "nor2": "nor", "xnor2": "xnor",
    "not1": "not", "buf1": "buf",
    "tie0": "tie0", "tie1": "tie1",
}
GATE_TO_COMPONENT = {v: k for k, v in COMPONENT_TO_GATE.items()}

ENTITY_RE = re.compile(
    r"entity\s+(\w+)\s+is\s+port\s*\(([^)]*)\)\s*;\s*end\s+entity\s*;", re.S | re.I
)
ARCH_RE = re.compile(
    r"architecture\s+\w+\s+of\s+\w+\s+is(.*?)begin(.*?)end\s+architecture\s*;",
    re.S | re.I,
)
SIGNAL_RE = re.compile(r"signal\s+([^;]+);", re.I)
INSTANCE_RE = re.compile(
    r"(\w+)\s*:\s*(" + "|".join(COMPONENT_TO_GATE) + r")\s+port\s+map\s*\(([^)]*)\)\s*;",
    re.I,
)


def parse_vhdl_netlist(source: str) -> Netlist:
    entity_match = ENTITY_RE.search(source)
    if not entity_match:
        raise ValueError("no entity/port declaration found")
    name, port_body = entity_match.group(1), entity_match.group(2)

    inputs, outputs = [], []
    for clause in port_body.split(";"):
        clause = clause.strip()
        if not clause:
            continue
        names_part, dir_part = clause.split(":")
        names = [n.strip() for n in names_part.split(",") if n.strip()]
        direction = dir_part.strip().lower().split()[0]
        if direction == "in":
            inputs.extend(names)
        elif direction == "out":
            outputs.extend(names)
        else:
            raise ValueError(f"unrecognized port direction: {clause!r}")

    arch_match = ARCH_RE.search(source)
    if not arch_match:
        raise ValueError("no architecture body found")
    decl_body, stmt_body = arch_match.group(1), arch_match.group(2)

    wires = []
    for m in SIGNAL_RE.finditer(decl_body):
        wires.extend(w.strip() for w in m.group(1).split(":")[0].split(",") if w.strip())

    gates = []
    for m in INSTANCE_RE.finditer(stmt_body):
        inst_name, component, portmap = m.group(1), m.group(2).lower(), m.group(3)
        assoc = {}
        for pair in portmap.split(","):
            key, _, val = pair.partition("=>")
            assoc[key.strip().lower()] = val.strip()

        output = assoc["o"]
        gate_inputs = [assoc[k] for k in sorted(assoc) if k != "o"]
        gates.append(Gate(COMPONENT_TO_GATE[component], inst_name, output, gate_inputs))

    return Netlist(name, inputs, outputs, wires, gates)


def render_vhdl(nl: Netlist) -> str:
    port_lines = []
    if nl.inputs:
        port_lines.append(f"{', '.join(nl.inputs)} : in std_logic")
    if nl.outputs:
        port_lines.append(f"{', '.join(nl.outputs)} : out std_logic")

    lines = [
        f"entity {nl.name} is",
        f"  port ({'; '.join(port_lines)});",
        "end entity;",
        "",
        f"architecture rtl of {nl.name} is",
    ]
    if nl.wires:
        lines.append(f"  signal {', '.join(nl.wires)} : std_logic;")
    lines.append("begin")
    for g in nl.gates:
        component = GATE_TO_COMPONENT[g.kind]
        if g.inputs:
            in_ports = ", ".join(f"i{i} => {w}" for i, w in enumerate(g.inputs))
            portmap = f"o => {g.output}, {in_ports}"
        else:
            portmap = f"o => {g.output}"
        lines.append(f"  {g.name}: {component} port map ({portmap});")
    lines.append("end architecture;")
    return "\n".join(lines)

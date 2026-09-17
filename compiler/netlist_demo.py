"""
Three small example circuits, one aimed at each pass, run through the full
netlist pipeline with equivalence checked by simulation after every run.

    python -m compiler.netlist_demo
"""

from .netlist import parse_netlist, render_netlist
from .vhdl_netlist import parse_vhdl_netlist, render_vhdl
from .netlist_passes import run_netlist_order
from .equivalence import check_equivalence

REDUNDANT_DEMO = """
module redundant_demo(input a, input b, input c, output y);
  wire w1, w2, w3, w4;
  and g1(w1, a, b);
  and g2(w2, a, b);
  or  g3(w3, w1, c);
  or  g4(w4, w2, c);
  xor g5(y, w3, w4);
endmodule
"""

DEAD_DEMO = """
module dead_demo(input a, input b, output y);
  wire w1, w2;
  and g1(w1, a, b);
  or  g2(w2, a, b);
  buf g3(y, w1);
endmodule
"""

CONST_DEMO = """
module const_demo(input a, output y);
  wire z, w1;
  tie0 t1(z);
  and g1(w1, a, z);
  or  g2(y, w1, a);
endmodule
"""

VHDL_REDUNDANT_DEMO = """
entity redundant_demo is
  port (a, b, c : in std_logic; y : out std_logic);
end entity;

architecture rtl of redundant_demo is
  signal w1, w2, w3, w4 : std_logic;
begin
  g1: and2 port map (o => w1, i0 => a, i1 => b);
  g2: and2 port map (o => w2, i0 => a, i1 => b);
  g3: or2 port map (o => w3, i0 => w1, i1 => c);
  g4: or2 port map (o => w4, i0 => w2, i1 => c);
  g5: xor2 port map (o => y, i0 => w3, i1 => w4);
end architecture;
"""

FULL_ORDER = ["const", "redundant", "dead"]


def run_demo(label, source):
    nl = parse_netlist(source)
    optimized, trace = run_netlist_order(nl, FULL_ORDER)
    ok, mode, n_checked = check_equivalence(nl, optimized)

    print(f"--- {label} ---")
    print(f"gates before: {len(nl.gates)}, gates after: {len(optimized.gates)}")
    for step in trace:
        if step["changed"]:
            print(f"  {step['pass']}: {step['gates_before']} -> {step['gates_after']} gates")
    print(f"equivalence check: {'PASSED' if ok else 'FAILED'} "
          f"({mode}, {n_checked} vectors)")
    print(render_netlist(optimized))
    print()
    return ok


def run_vhdl_demo(label, source):
    nl = parse_vhdl_netlist(source)
    optimized, trace = run_netlist_order(nl, FULL_ORDER)
    ok, mode, n_checked = check_equivalence(nl, optimized)

    print(f"--- {label} (parsed from VHDL) ---")
    print(f"gates before: {len(nl.gates)}, gates after: {len(optimized.gates)}")
    for step in trace:
        if step["changed"]:
            print(f"  {step['pass']}: {step['gates_before']} -> {step['gates_after']} gates")
    print(f"equivalence check: {'PASSED' if ok else 'FAILED'} "
          f"({mode}, {n_checked} vectors)")
    print(render_vhdl(optimized))
    print()
    return ok


if __name__ == "__main__":
    results = [
        run_demo("redundant gate elimination", REDUNDANT_DEMO),
        run_demo("dead gate elimination", DEAD_DEMO),
        run_demo("constant propagation", CONST_DEMO),
        run_vhdl_demo("redundant gate elimination", VHDL_REDUNDANT_DEMO),
    ]
    assert all(results), "an equivalence check failed"
    print("all demos verified equivalent, in both Verilog and VHDL")

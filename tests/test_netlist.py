import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compiler.netlist import parse_netlist, render_netlist
from compiler.vhdl_netlist import parse_vhdl_netlist, render_vhdl
from compiler.netlist_sim import simulate, all_input_vectors
from compiler.netlist_passes import (
    redundant_gate_elimination,
    dead_gate_elimination,
    constant_propagation,
    run_netlist_order,
)
from compiler.equivalence import check_equivalence


HALF_ADDER = """
module half_adder(input a, input b, output sum, output carry);
  and g1(carry, a, b);
  xor g2(sum, a, b);
endmodule
"""


def test_parse_reports_correct_ports_and_gate_count():
    nl = parse_netlist(HALF_ADDER)
    assert nl.inputs == ["a", "b"]
    assert nl.outputs == ["sum", "carry"]
    assert len(nl.gates) == 2


def test_simulate_matches_truth_table_for_and_gate():
    nl = parse_netlist("module m(input a, input b, output y);\n  and g1(y, a, b);\nendmodule\n")
    assert simulate(nl, {"a": 0, "b": 0})["y"] == 0
    assert simulate(nl, {"a": 1, "b": 0})["y"] == 0
    assert simulate(nl, {"a": 1, "b": 1})["y"] == 1


def test_redundant_gate_elimination_merges_duplicate_gate():
    nl = parse_netlist("""
        module m(input a, input b, output y, output z);
          and g1(y, a, b);
          and g2(z, a, b);
        endmodule
    """)
    reduced, changed = redundant_gate_elimination(nl)
    assert changed
    assert len(reduced.gates) == 1


def test_dead_gate_elimination_drops_unused_gate():
    nl = parse_netlist("""
        module m(input a, input b, output y);
          and g1(y, a, b);
          or g2(w1, a, b);
        endmodule
    """)
    reduced, changed = dead_gate_elimination(nl)
    assert changed
    assert len(reduced.gates) == 1


def test_constant_propagation_folds_and_with_zero_input():
    nl = parse_netlist("""
        module m(input a, output y);
          wire z;
          tie0 t1(z);
          and g1(y, a, z);
        endmodule
    """)
    reduced, changed = constant_propagation(nl)
    assert changed
    assert reduced.gates[-1].kind == "tie0"


def test_every_pass_preserves_behavior_on_all_three_demos():
    from compiler.netlist_demo import REDUNDANT_DEMO, DEAD_DEMO, CONST_DEMO
    for source in (REDUNDANT_DEMO, DEAD_DEMO, CONST_DEMO):
        nl = parse_netlist(source)
        optimized, _ = run_netlist_order(nl, ["const", "redundant", "dead"])
        ok, _, _ = check_equivalence(nl, optimized)
        assert ok


def test_render_netlist_round_trips_through_parser():
    nl = parse_netlist(HALF_ADDER)
    rendered = render_netlist(nl)
    reparsed = parse_netlist(rendered)
    assert reparsed.inputs == nl.inputs
    assert reparsed.outputs == nl.outputs
    assert len(reparsed.gates) == len(nl.gates)


VHDL_HALF_ADDER = """
entity half_adder is
  port (a, b : in std_logic; sum, carry : out std_logic);
end entity;

architecture rtl of half_adder is
begin
  g1: and2 port map (o => carry, i0 => a, i1 => b);
  g2: xor2 port map (o => sum, i0 => a, i1 => b);
end architecture;
"""


def test_vhdl_parser_matches_verilog_parser_on_same_circuit():
    verilog_nl = parse_netlist(HALF_ADDER)
    vhdl_nl = parse_vhdl_netlist(VHDL_HALF_ADDER)
    assert set(verilog_nl.inputs) == set(vhdl_nl.inputs)
    assert set(verilog_nl.outputs) == set(vhdl_nl.outputs)
    ok, _, _ = check_equivalence(verilog_nl, vhdl_nl)
    assert ok


def test_vhdl_netlist_survives_the_same_passes_as_verilog():
    nl = parse_vhdl_netlist("""
        entity m is
          port (a, b, c : in std_logic; y : out std_logic);
        end entity;

        architecture rtl of m is
          signal w1, w2 : std_logic;
        begin
          g1: and2 port map (o => w1, i0 => a, i1 => b);
          g2: and2 port map (o => w2, i0 => a, i1 => b);
          g3: or2 port map (o => y, i0 => w1, i1 => w2);
        end architecture;
    """)
    optimized, trace = run_netlist_order(nl, ["redundant", "dead", "const"])
    assert len(optimized.gates) < len(nl.gates)
    ok, _, _ = check_equivalence(nl, optimized)
    assert ok


def test_render_vhdl_round_trips_through_its_own_parser():
    nl = parse_vhdl_netlist(VHDL_HALF_ADDER)
    rendered = render_vhdl(nl)
    reparsed = parse_vhdl_netlist(rendered)
    assert reparsed.inputs == nl.inputs
    assert reparsed.outputs == nl.outputs
    assert len(reparsed.gates) == len(nl.gates)

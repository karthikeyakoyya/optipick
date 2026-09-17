# OptiPick

A small compiler that learns which order to run its own optimization passes in,
instead of using one order an engineer fixed in advance.

Every real compiler applies passes like constant folding, dead code elimination,
and loop invariant code motion in some sequence. That sequence is normally chosen
once, by hand, and never revisited. OptiPick generates hundreds of small
synthetic programs, tries several sensible pass orders on each one, measures how
much total work each order takes to reach the same optimized result, and trains
a shallow decision tree to predict the cheaper order from a handful of simple
properties of a program (its size, how many values are already constants,
whether it has a loop).

Open `visualizer/index.html` in a browser to see it work: a source program
compiles to a small three address intermediate form, the four passes apply one
at a time while the instruction count ticks down, and a second panel walks
through the actual decision tree path chosen for a real training example,
alongside honest numbers on how often the learned order helps.

## What is real here and what is simplified

Everything in `compiler/` runs and is tested; nothing in the demo is staged or
faked. That said, this is a teaching sized project, not a production compiler,
and it is worth being upfront about where it cuts corners:

* The intermediate form is a flat three address code with labels and gotos,
  not a real control flow graph. Constant folding and common subexpression
  elimination are conservative around labels rather than using dominance
  information.
* Loop invariant code motion recognizes a loop as a label whose name is later
  targeted by a goto, and hoists instructions whose operands are never
  reassigned inside that region. It does not build a full loop nest structure,
  so nested loops are handled one at a time rather than jointly.
* Dead code elimination treats any named (non temporary) variable as a
  possible program output, since the toy language has no explicit output
  statement, and only removes compiler generated temporaries that are never
  read.
* The training set is randomly generated small programs, around 260 of them,
  not real world source code. The reported accuracy (roughly 90% on programs
  held out during training) and the average work saving (about 2.4%, up to
  8.4% in the best case measured) describe this synthetic benchmark, and
  should be read as a demonstration of the idea rather than a production
  result.
* Six candidate pass orders were compared, not all 24 possible orderings of
  four passes, chosen to keep the training data and the resulting decision
  tree small enough to read end to end.

## Two optimizers, one shared idea

OptiPick actually has two halves now:

* The program compiler described above: a toy language, three address IR,
  and four passes, with a decision tree choosing what order to run them in.
* A gate level netlist optimizer (`compiler/netlist.py`, `netlist_sim.py`,
  `netlist_passes.py`, `equivalence.py`) that applies the same underlying
  idea, redundant work should be reused and dead work should be dropped,
  to circuits instead of programs.

The netlist side parses a small structural Verilog subset (primitive gates
wired together, the shape a design takes after synthesis has already
broken it down to and/or/not/xor/nand/nor/buf/xnor), plus the same shape
written as structural VHDL (`compiler/vhdl_netlist.py`, entity/port
declarations and an architecture body instantiating primitive gate
components with named port maps). Both parsers build the same Netlist
and Gate objects, so the simulator, the three passes, and the equivalence
checker did not need any changes to support the second language, they
already operated on the shared representation rather than on source text.
SystemVerilog (IEEE 1800) was merged with the base Verilog standard in
2009 and is an extension of it, so the same gate-primitive subset the
Verilog parser reads is valid SystemVerilog too.

Then it runs three passes over the resulting graph: redundant gate
elimination (two gates computing the same function of the same inputs
get merged), dead gate elimination (a gate nothing reads gets dropped),
and constant propagation (a gate whose inputs are already known 0 or 1
folds to a constant). Every optimized circuit is checked against the
original by simulating both on every possible input combination (or a
random sample once the input count gets too large to enumerate) and
asserting the outputs match exactly, so a pass that changed behavior
would fail its own test rather than silently shipping.

Run `python3 -m compiler.netlist_demo` to see four small circuits (three
in Verilog, one in VHDL, one aimed at each pass) optimized and verified
end to end, with the resulting source printed out.

This part is intentionally scoped small: no multi-bit buses, no sequential
elements (flip-flops, clocks), no real synthesis. It is a working
demonstration of applying compiler style optimization theory to hardware
logic and proving correctness by simulation, not a synthesis tool.



```
compiler/
  lexer.py            tokenizer for the toy language
  parser.py           recursive descent parser producing an AST
  ir.py               three address code generator
  passes.py           the four optimization passes
  pipeline.py         runs a chosen pass order to a fixed point, with a trace
  features.py         extracts a feature vector from raw IR
  programgen.py       generates random programs for training data
  train_selector.py   builds the dataset and trains the decision tree
  selector.py         loads the trained tree and predicts a pass order
  export_trace.py     runs two demo programs and writes visualizer/trace.json
  selector_model.json the trained tree, saved as plain JSON
  netlist.py          structural Verilog parser and netlist data structures
  vhdl_netlist.py      structural VHDL parser and printer, same Netlist type
  netlist_sim.py       gate level combinational simulator
  netlist_passes.py    redundant/dead gate elimination and constant propagation
  equivalence.py       simulation based equivalence checking between netlists
  netlist_demo.py      runs three example circuits through the netlist passes

tests/
  test_compiler.py    covers the lexer through pipeline, plus the selector
  test_netlist.py     covers both the Verilog and VHDL parsers, the
                       simulator, the passes, and the equivalence checker

visualizer/
  index.html          the built, self contained demo page (open this one)
  template.html        the source template build.py fills in
  build.py             injects trace.json into template.html
  trace.json           the exported trace the page reads
```

## Running it yourself

```
cd optipick
python3 -m pytest tests/ -v          # 17 tests, no external services needed
python3 -m compiler.train_selector   # regenerates selector_model.json
python3 -m compiler.export_trace     # regenerates visualizer/trace.json
python3 visualizer/build.py          # rebuilds visualizer/index.html
python3 -m compiler.netlist_demo     # runs the netlist optimizer demos
```

Everything runs on the standard library plus scikit-learn (only needed for
`train_selector.py`; the compiler itself has no dependencies).

## Why this project

It sits in the specific gap between compiler engineering and applied machine
learning: not writing a compiler for its own sake, and not training a model on
a problem chosen because data was easy to get. The interesting part is the
honest result in `selector_model.json` and in the visualizer's final section:
pass order genuinely does not matter for the majority of small, simple
programs, and matters by a small but real and measurable amount once a program
has enough redundant computation and loop structure for order to change how
much work the compiler does to reach the same answer.

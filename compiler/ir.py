"""
Three address code generation.

Every instruction is one of:
    const  dest value
    copy   dest src
    binop  dest op a b
    label  name
    goto   name
    if_false cond label

Constants are always materialized into a temp before use, and every
arithmetic or comparison result lands in a fresh temp, which is what makes
constant folding, copy propagation, common subexpression elimination and
loop invariant code motion tractable without a full control flow graph.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Instr:
    op: str
    dest: Optional[str] = None
    a: Optional[str] = None
    b: Optional[str] = None
    value: Optional[float] = None
    label: Optional[str] = None

    def copy(self):
        return Instr(self.op, self.dest, self.a, self.b, self.value, self.label)

    def render(self):
        if self.op == "const":
            return f"{self.dest} = {self.value}"
        if self.op == "copy":
            return f"{self.dest} = {self.a}"
        if self.op == "binop":
            return f"{self.dest} = {self.a} {self.b_op} {self.b}"
        if self.op == "label":
            return f"{self.label}:"
        if self.op == "goto":
            return f"goto {self.label}"
        if self.op == "if_false":
            return f"if_false {self.a} goto {self.label}"
        return str(self)


# binop needs an extra operator slot; reuse `value` field to store it as string
# to keep the dataclass small. Add a friendly accessor.
def _b_op(self):
    return self.value


Instr.b_op = property(_b_op)


class IRBuilder:
    def __init__(self):
        self.code = []
        self._temp_count = 0
        self._label_count = 0

    def new_temp(self):
        self._temp_count += 1
        return f"t{self._temp_count}"

    def new_label(self):
        self._label_count += 1
        return f"L{self._label_count}"

    def emit(self, instr):
        self.code.append(instr)

    def gen_expr(self, node):
        if node.kind == "const":
            dest = self.new_temp()
            self.emit(Instr("const", dest=dest, value=node.value))
            return dest
        if node.kind == "var":
            return node.name
        if node.kind == "binop":
            a = self.gen_expr(node.left)
            b = self.gen_expr(node.right)
            dest = self.new_temp()
            self.emit(Instr("binop", dest=dest, a=a, b=b, value=node.op))
            return dest
        raise ValueError(f"unknown expr node {node.kind}")

    def gen_stmt(self, node):
        if node.kind == "assign":
            src = self.gen_expr(node.value)
            self.emit(Instr("copy", dest=node.target, a=src))
        elif node.kind == "if":
            cond = self.gen_expr(node.cond)
            end_label = self.new_label()
            self.emit(Instr("if_false", a=cond, label=end_label))
            for s in node.body:
                self.gen_stmt(s)
            self.emit(Instr("label", label=end_label))
        elif node.kind == "while":
            start_label = self.new_label()
            end_label = self.new_label()
            self.emit(Instr("label", label=start_label))
            cond = self.gen_expr(node.cond)
            self.emit(Instr("if_false", a=cond, label=end_label))
            for s in node.body:
                self.gen_stmt(s)
            self.emit(Instr("goto", label=start_label))
            self.emit(Instr("label", label=end_label))
        else:
            raise ValueError(f"unknown stmt node {node.kind}")

    def gen_program(self, node):
        for s in node.body:
            self.gen_stmt(s)
        return self.code


def generate(ast):
    builder = IRBuilder()
    return builder.gen_program(ast)


def render_ir(code):
    return [instr.render() for instr in code]

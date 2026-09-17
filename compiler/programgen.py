"""
Generates random, syntactically valid programs in the toy language so we
have a training set for the pass order selector without hand writing
hundreds of examples. Every generated program actually parses; this walks
the same grammar the parser accepts, just building source text instead of
reading it.
"""

import random


def random_expr(rng, vars_in_scope, const_bias, depth=0):
    if depth >= 2 or rng.random() < const_bias:
        return str(rng.randint(1, 9))
    choice = rng.random()
    if choice < 0.5 and vars_in_scope:
        return rng.choice(vars_in_scope)
    op = rng.choice(["+", "-", "*"])
    left = random_expr(rng, vars_in_scope, const_bias, depth + 1)
    right = random_expr(rng, vars_in_scope, const_bias, depth + 1)
    return f"({left} {op} {right})"


def random_program(rng, n_vars=4, n_stmts=8, const_bias=0.5,
                    duplicate_chance=0.3, loop_chance=0.6):
    var_names = [f"v{i}" for i in range(n_vars)]
    lines = []
    for v in var_names:
        lines.append(f"{v} = {rng.randint(1, 9)};")

    last_expr = None
    for _ in range(n_stmts):
        target = rng.choice(var_names)
        if last_expr is not None and rng.random() < duplicate_chance:
            expr = last_expr
        else:
            expr = random_expr(rng, var_names, const_bias)
            last_expr = expr
        lines.append(f"{target} = {expr};")

    if rng.random() < loop_chance:
        counter = rng.choice(var_names)
        limit = rng.randint(2, 6)
        invariant_target = rng.choice(var_names)
        invariant_expr = random_expr(rng, [], const_bias=1.0)
        body_target = rng.choice(var_names)
        lines.append(f"{counter} = 0;")
        lines.append(f"while ({counter} < {limit}) {{")
        lines.append(f"  {invariant_target} = {invariant_expr};")
        lines.append(f"  {body_target} = {body_target} + {invariant_target};")
        lines.append(f"  {counter} = {counter} + 1;")
        lines.append("}")

    return "\n".join(lines) + "\n"


def make_corpus(n_programs, seed=7):
    rng = random.Random(seed)
    programs = []
    for _ in range(n_programs):
        n_vars = rng.randint(2, 5)
        n_stmts = rng.randint(4, 10)
        const_bias = rng.uniform(0.2, 0.8)
        duplicate_chance = rng.uniform(0.0, 0.5)
        loop_chance = rng.uniform(0.3, 0.9)
        programs.append(random_program(rng, n_vars, n_stmts, const_bias,
                                        duplicate_chance, loop_chance))
    return programs

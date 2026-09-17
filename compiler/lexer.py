"""
Tokenizer for the toy language OptiPick compiles.

The language is deliberately small: assignments, arithmetic, comparisons,
if blocks and while loops. Just enough surface syntax to produce interesting
three address code for the optimizer passes to chew on.
"""

import re
from collections import namedtuple

Token = namedtuple("Token", ["kind", "value", "pos"])

TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d+)?"),
    ("ID",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",       r"==|<=|>=|[+\-*/<>]"),
    ("ASSIGN",   r"="),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("SEMI",     r";"),
    ("SKIP",     r"[ \t]+"),
    ("NEWLINE",  r"\n"),
    ("COMMENT",  r"//[^\n]*"),
]

KEYWORDS = {"if", "while"}

MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


def tokenize(source: str):
    tokens = []
    for match in MASTER_RE.finditer(source):
        kind = match.lastgroup
        value = match.group()
        pos = match.start()
        if kind in ("SKIP", "NEWLINE", "COMMENT"):
            continue
        if kind == "ID" and value in KEYWORDS:
            kind = value.upper()
        tokens.append(Token(kind, value, pos))
    tokens.append(Token("EOF", "", len(source)))
    return tokens

"""
A small recursive descent parser. Grammar:

    program   := stmt*
    stmt      := assign | if_stmt | while_stmt
    assign    := ID '=' expr ';'
    if_stmt   := 'if' '(' expr ')' '{' stmt* '}'
    while_stmt:= 'while' '(' expr ')' '{' stmt* '}'
    expr      := term (('+'|'-'|'*'|'/'|'<'|'>'|'<='|'>='|'==') term)*
    term      := NUMBER | ID | '(' expr ')'
"""

from .lexer import tokenize


class Node:
    def __init__(self, kind, **fields):
        self.kind = kind
        self.__dict__.update(fields)

    def __repr__(self):
        fields = {k: v for k, v in self.__dict__.items() if k != "kind"}
        return f"{self.kind}({fields})"


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def advance(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, kind):
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(f"expected {kind}, got {tok.kind} ({tok.value!r}) at {tok.pos}")
        return self.advance()

    def parse_program(self):
        stmts = []
        while self.peek().kind != "EOF":
            stmts.append(self.parse_stmt())
        return Node("program", body=stmts)

    def parse_stmt(self):
        tok = self.peek()
        if tok.kind == "IF":
            return self.parse_if()
        if tok.kind == "WHILE":
            return self.parse_while()
        return self.parse_assign()

    def parse_assign(self):
        name = self.expect("ID").value
        self.expect("ASSIGN")
        value = self.parse_expr()
        self.expect("SEMI")
        return Node("assign", target=name, value=value)

    def parse_if(self):
        self.expect("IF")
        self.expect("LPAREN")
        cond = self.parse_expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        body = []
        while self.peek().kind != "RBRACE":
            body.append(self.parse_stmt())
        self.expect("RBRACE")
        return Node("if", cond=cond, body=body)

    def parse_while(self):
        self.expect("WHILE")
        self.expect("LPAREN")
        cond = self.parse_expr()
        self.expect("RPAREN")
        self.expect("LBRACE")
        body = []
        while self.peek().kind != "RBRACE":
            body.append(self.parse_stmt())
        self.expect("RBRACE")
        return Node("while", cond=cond, body=body)

    def parse_expr(self):
        left = self.parse_term()
        while self.peek().kind == "OP":
            op = self.advance().value
            right = self.parse_term()
            left = Node("binop", op=op, left=left, right=right)
        return left

    def parse_term(self):
        tok = self.peek()
        if tok.kind == "NUMBER":
            self.advance()
            value = float(tok.value) if "." in tok.value else int(tok.value)
            return Node("const", value=value)
        if tok.kind == "ID":
            self.advance()
            return Node("var", name=tok.value)
        if tok.kind == "LPAREN":
            self.advance()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr
        raise ParseError(f"unexpected token {tok.kind} ({tok.value!r}) at {tok.pos}")


def parse(source: str):
    tokens = tokenize(source)
    return Parser(tokens).parse_program()

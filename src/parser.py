from dataclasses import dataclass
from src.lexer import Token, TokenKind

MAX_I32 = 2147483647
MAX_I64 = 9223372036854775807

class ParserError(Exception):
    def __init__(self, line: int, col: int, message: str) -> None:
        self.line = line
        self.col = col
        self.message = message
        super().__init__(f"compilation error: line {line}:{col}: {message}")

# --- AST Nodes ---

@dataclass(slots=True)
class ASTNode:
    line: int
    col: int

    def dump(self, indent: int = 0) -> str:
        raise NotImplementedError

type StatementNode = DeclNode | AssignNode | IfStmtNode | ExitStmtNode
type ExprNode = BinOpNode | LiteralNode | VarNode

@dataclass(slots=True)
class ProgramNode(ASTNode):
    statements: list[StatementNode]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Program"]
        for stmt in self.statements:
            lines.append(stmt.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class DeclNode(ASTNode):
    kind: str
    type_name: str
    name: str
    expr: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Decl {self.name} {self.type_name} {self.kind}"]
        lines.append(self.expr.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class AssignNode(ASTNode):
    name: str
    op: str
    expr: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Assign {self.name}"]
        lines.append(self.expr.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class IfStmtNode(ASTNode):
    cond: ExprNode
    then_body: list[StatementNode]
    else_body: list[StatementNode] | None

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}If"]
        lines.append(f"{sp}  Condition")
        lines.append(self.cond.dump(indent + 4))
        lines.append(f"{sp}  Then")
        for s in self.then_body:
            lines.append(s.dump(indent + 4))
        if self.else_body is not None:
            lines.append(f"{sp}  Else")
            for s in self.else_body:
                lines.append(s.dump(indent + 4))
        return "\n".join(lines)

@dataclass(slots=True)
class ExitStmtNode(ASTNode):
    expr: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Exit"]
        lines.append(self.expr.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class BinOpNode(ASTNode):
    op: str
    left: ExprNode
    right: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}BinOp {self.op}"]
        lines.append(self.left.dump(indent + 2))
        lines.append(self.right.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class LiteralNode(ASTNode):
    value: int | bool
    type_name: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        if isinstance(self.value, bool):
            val_str = "hot" if self.value else "cringe"
            return f"{sp}Bool {val_str}"
        return f"{sp}{self.value}"

@dataclass(slots=True)
class VarNode(ASTNode):
    name: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        return f"{sp}Var {self.name}"

# --- Recursive Descent Parser ---

class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def _eat(self, expected_kind: TokenKind) -> Token:
        tok = self._peek()
        if tok.kind != expected_kind:
            raise ParserError(tok.line, tok.col, f"expected '{expected_kind}', got '{tok.text or tok.kind}'")
        self.pos += 1
        return tok

    def parse(self) -> ProgramNode:
        prog_line = self._peek().line
        prog_col = self._peek().col
        statements: list[StatementNode] = []

        while self._peek().kind != TokenKind.EOF:
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
                continue
            stmt = self.parse_statement()
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
            statements.append(stmt)

        return ProgramNode(line=prog_line, col=prog_col, statements=statements)

    def parse_statement(self) -> StatementNode:
        tok = self._peek()
        match tok.kind:
            case TokenKind.CANON | TokenKind.YAP | TokenKind.CANONMAXING:
                return self.parse_decl()
            case TokenKind.IDENT:
                return self.parse_assign()
            case TokenKind.IS_THIS_REAL:
                return self.parse_if()
            case TokenKind.EXIT:
                return self.parse_exit()
            case _:
                raise ParserError(tok.line, tok.col, f"unexpected token '{tok.text or tok.kind}' at start of statement")

    def parse_decl(self) -> DeclNode:
        kind_tok = self._peek()
        self.pos += 1

        type_tok = self._peek()
        if type_tok.kind not in (TokenKind.TYPE_NPC, TokenKind.TYPE_SIGMA, TokenKind.TYPE_TAKE):
            raise ParserError(type_tok.line, type_tok.col, f"expected type ('npc', 'sigma', 'take'), got '{type_tok.text or type_tok.kind}'")
        self.pos += 1

        name_tok = self._eat(TokenKind.IDENT)

        assign_tok = self._peek()
        if assign_tok.kind not in (TokenKind.ASSIGN, TokenKind.EMOJI_ASSIGN):
            raise ParserError(assign_tok.line, assign_tok.col, f"expected ':=' or '👈🏻', got '{assign_tok.text or assign_tok.kind}'")
        self.pos += 1

        expr = self.parse_expr()

        # Check integer overflow for npc (i32)
        if type_tok.kind == TokenKind.TYPE_NPC and isinstance(expr, LiteralNode) and isinstance(expr.value, int):
            if expr.value > MAX_I32:
                raise ParserError(expr.line, expr.col, f"integer literal overflow: '{expr.value}' exceeds 32-bit integer range for type 'npc'")

        return DeclNode(
            line=kind_tok.line,
            col=kind_tok.col,
            kind=kind_tok.text,
            type_name=type_tok.text,
            name=name_tok.text,
            expr=expr,
        )

    def parse_assign(self) -> AssignNode:
        name_tok = self._eat(TokenKind.IDENT)

        assign_tok = self._peek()
        if assign_tok.kind not in (TokenKind.ASSIGN, TokenKind.EMOJI_ASSIGN):
            raise ParserError(assign_tok.line, assign_tok.col, f"expected ':=' or '👈🏻', got '{assign_tok.text or assign_tok.kind}'")
        self.pos += 1

        expr = self.parse_expr()
        return AssignNode(
            line=name_tok.line,
            col=name_tok.col,
            name=name_tok.text,
            op=assign_tok.text,
            expr=expr,
        )

    def parse_if(self) -> IfStmtNode:
        if_tok = self._eat(TokenKind.IS_THIS_REAL)
        cond = self.parse_expr()

        self._eat(TokenKind.LBRACE)
        then_body: list[StatementNode] = []
        while self._peek().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
                continue
            stmt = self.parse_statement()
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
            then_body.append(stmt)

        if not then_body:
            raise ParserError(self._peek().line, self._peek().col, "expected at least one statement in 'is_this_real' block")
        self._eat(TokenKind.RBRACE)

        else_body: list[StatementNode] | None = None
        if self._peek().kind == TokenKind.NAH:
            self.pos += 1
            self._eat(TokenKind.LBRACE)
            else_body = []
            while self._peek().kind not in (TokenKind.RBRACE, TokenKind.EOF):
                if self._peek().kind == TokenKind.SEMICOLON:
                    self.pos += 1
                    continue
                stmt = self.parse_statement()
                if self._peek().kind == TokenKind.SEMICOLON:
                    self.pos += 1
                else_body.append(stmt)
            if not else_body:
                raise ParserError(self._peek().line, self._peek().col, "expected at least one statement in 'nah' block")
            self._eat(TokenKind.RBRACE)

        return IfStmtNode(
            line=if_tok.line,
            col=if_tok.col,
            cond=cond,
            then_body=then_body,
            else_body=else_body,
        )

    def parse_exit(self) -> ExitStmtNode:
        exit_tok = self._eat(TokenKind.EXIT)
        factor = self.parse_factor()
        return ExitStmtNode(line=exit_tok.line, col=exit_tok.col, expr=factor)

    def parse_expr(self) -> ExprNode:
        left = self.parse_arith()

        comp_tok = self._peek()
        if comp_tok.kind in (TokenKind.EQ, TokenKind.NEQ, TokenKind.EMOJI_EQ, TokenKind.EMOJI_NEQ):
            self.pos += 1
            right = self.parse_arith()

            # Prevent double comparisons: a == b == c
            next_comp = self._peek()
            if next_comp.kind in (TokenKind.EQ, TokenKind.NEQ, TokenKind.EMOJI_EQ, TokenKind.EMOJI_NEQ):
                raise ParserError(next_comp.line, next_comp.col, "multiple comparisons in a single expression are not allowed")

            return BinOpNode(
                line=comp_tok.line,
                col=comp_tok.col,
                op=comp_tok.text,
                left=left,
                right=right,
            )

        return left

    def parse_arith(self) -> ExprNode:
        left = self.parse_term()

        while self._peek().kind in (TokenKind.PLUS, TokenKind.MINUS):
            op_tok = self._peek()
            self.pos += 1
            right = self.parse_term()
            left = BinOpNode(
                line=op_tok.line,
                col=op_tok.col,
                op=op_tok.text,
                left=left,
                right=right,
            )

        return left

    def parse_term(self) -> ExprNode:
        left = self.parse_factor()

        while self._peek().kind == TokenKind.STAR:
            op_tok = self._peek()
            self.pos += 1
            right = self.parse_factor()
            left = BinOpNode(
                line=op_tok.line,
                col=op_tok.col,
                op=op_tok.text,
                left=left,
                right=right,
            )

        return left

    def parse_factor(self) -> ExprNode:
        tok = self._peek()
        match tok.kind:
            case TokenKind.NUMBER:
                self.pos += 1
                val = int(tok.text)
                if val > MAX_I64:
                    raise ParserError(tok.line, tok.col, f"integer literal overflow: '{tok.text}' exceeds 64-bit integer range")
                return LiteralNode(line=tok.line, col=tok.col, value=val, type_name="number")
            case TokenKind.HOT:
                self.pos += 1
                return LiteralNode(line=tok.line, col=tok.col, value=True, type_name="take")
            case TokenKind.CRINGE:
                self.pos += 1
                return LiteralNode(line=tok.line, col=tok.col, value=False, type_name="take")
            case TokenKind.IDENT:
                self.pos += 1
                return VarNode(line=tok.line, col=tok.col, name=tok.text)
            case TokenKind.LPAREN:
                self.pos += 1
                expr = self.parse_expr()
                self._eat(TokenKind.RPAREN)
                return expr
            case _:
                raise ParserError(tok.line, tok.col, f"expected expression factor (number, hot, cringe, identifier, or '('), got '{tok.text or tok.kind}'")

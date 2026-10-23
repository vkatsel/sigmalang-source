from dataclasses import dataclass, field
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

@dataclass(slots=True)
class StmtNode(ASTNode):
    pass

@dataclass(slots=True)
class ExprNode(ASTNode):
    pass

type StatementNode = StmtNode

@dataclass(slots=True)
class ProgramNode(ASTNode):
    statements: list[StmtNode]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Program"]
        for stmt in self.statements:
            lines.append(stmt.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class FieldDef:
    kind: str
    type_name: str
    name: str
    line: int
    col: int

@dataclass(slots=True)
class SquadDefNode(StmtNode):
    name: str
    fields: list[FieldDef]
    methods: list["LoreDefNode"]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Squad {self.name}"]
        for f in self.fields:
            lines.append(f"{sp}  Field {f.name} {f.type_name} {f.kind}")
        for m in self.methods:
            lines.append(m.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class ParamDef:
    type_name: str
    name: str
    line: int
    col: int

@dataclass(slots=True)
class LoreDefNode(StmtNode):
    name: str
    params: list[ParamDef]
    return_type: str
    body: list[StmtNode]
    is_member: bool = False

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        tag = "MemberLore" if self.is_member else "Lore"
        params_str = ", ".join(f"{p.type_name} {p.name}" for p in self.params)
        lines = [f"{sp}{tag} {self.name}({params_str}) -> {self.return_type}"]
        for stmt in self.body:
            lines.append(stmt.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class SquadInitNode(ExprNode):
    elements: list[ExprNode]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}SquadInit"]
        for elem in self.elements:
            lines.append(elem.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class DeclNode(StmtNode):
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
class AssignNode(StmtNode):
    name: str
    op: str
    expr: ExprNode
    fields: list[str] = field(default_factory=list)

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        if self.fields:
            chain = ".".join([self.name, *self.fields])
            lines = [f"{sp}FieldAssign {chain}"]
        else:
            lines = [f"{sp}Assign {self.name}"]
        lines.append(self.expr.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class PrintStmtNode(StmtNode):
    arg: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Print"]
        lines.append(self.arg.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class IfStmtNode(StmtNode):
    cond: ExprNode
    then_body: list[StmtNode]
    else_body: list[StmtNode] | None

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
class ExitStmtNode(StmtNode):
    expr: ExprNode

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Exit"]
        lines.append(self.expr.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class BinOpNode(ExprNode):
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
class LiteralNode(ExprNode):
    value: int | bool
    type_name: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        if isinstance(self.value, bool):
            val_str = "hot" if self.value else "cringe"
            return f"{sp}Bool {val_str}"
        return f"{sp}Number {self.value}"

@dataclass(slots=True)
class StringLiteralNode(ExprNode):
    value: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        return f'{sp}String "{self.value}"'

@dataclass(slots=True)
class ReadNode(ExprNode):
    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        return f"{sp}Read"

@dataclass(slots=True)
class VarNode(ExprNode):
    name: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        return f"{sp}Var {self.name}"

@dataclass(slots=True)
class CallNode(ExprNode):
    func_name: str
    args: list[ExprNode]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}Call {self.func_name}"]
        for a in self.args:
            lines.append(a.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class FieldAccessNode(ExprNode):
    target: ExprNode
    field_name: str

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}FieldAccess {self.field_name}"]
        lines.append(self.target.dump(indent + 2))
        return "\n".join(lines)

@dataclass(slots=True)
class MemberCallNode(ExprNode):
    target: ExprNode
    method_name: str
    args: list[ExprNode]

    def dump(self, indent: int = 0) -> str:
        sp = " " * indent
        lines = [f"{sp}MemberCall {self.method_name}"]
        lines.append(self.target.dump(indent + 2))
        for a in self.args:
            lines.append(a.dump(indent + 2))
        return "\n".join(lines)

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
            match self._peek().kind:
                case TokenKind.SQUAD:
                    statements.append(self.parse_squad_def())
                case TokenKind.LORE:
                    statements.append(self.parse_lore_def(is_member=False))
                case _:
                    stmt = self.parse_statement()
                    statements.append(stmt)
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1

        return ProgramNode(line=prog_line, col=prog_col, statements=statements)

    def parse_squad_def(self) -> SquadDefNode:
        squad_tok = self._eat(TokenKind.SQUAD)
        name_tok = self._eat(TokenKind.IDENT)
        self._eat(TokenKind.LBRACE)

        fields: list[FieldDef] = []
        methods: list[LoreDefNode] = []

        # Parse fields first
        while self._peek().kind in (TokenKind.CANON, TokenKind.YAP, TokenKind.CANONMAXING):
            kind_tok = self._peek()
            self.pos += 1
            type_tok = self.parse_type()
            fname_tok = self._eat(TokenKind.IDENT)
            fields.append(FieldDef(
                kind=kind_tok.text,
                type_name=type_tok.text,
                name=fname_tok.text,
                line=fname_tok.line,
                col=fname_tok.col,
            ))
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1

        if not fields:
            tok = self._peek()
            raise ParserError(tok.line, tok.col, "expected at least one field in 'squad'")

        # Parse member functions
        while self._peek().kind == TokenKind.LORE:
            methods.append(self.parse_lore_def(is_member=True))

        if self._peek().kind in (TokenKind.CANON, TokenKind.YAP, TokenKind.CANONMAXING):
            tok = self._peek()
            raise ParserError(tok.line, tok.col, "fields must be declared before member functions in 'squad'")

        self._eat(TokenKind.RBRACE)
        return SquadDefNode(
            line=squad_tok.line,
            col=squad_tok.col,
            name=name_tok.text,
            fields=fields,
            methods=methods,
        )

    def parse_lore_def(self, is_member: bool = False) -> LoreDefNode:
        lore_tok = self._eat(TokenKind.LORE)
        name_tok = self._eat(TokenKind.IDENT)
        self._eat(TokenKind.LPAREN)

        params: list[ParamDef] = []
        if self._peek().kind != TokenKind.RPAREN:
            ptype_tok = self.parse_type()
            pname_tok = self._eat(TokenKind.IDENT)
            params.append(ParamDef(type_name=ptype_tok.text, name=pname_tok.text, line=pname_tok.line, col=pname_tok.col))
            while self._peek().kind == TokenKind.COMMA:
                self.pos += 1
                ptype_tok = self.parse_type()
                pname_tok = self._eat(TokenKind.IDENT)
                params.append(ParamDef(type_name=ptype_tok.text, name=pname_tok.text, line=pname_tok.line, col=pname_tok.col))

        self._eat(TokenKind.RPAREN)
        self._eat(TokenKind.ARROW)
        ret_type_tok = self.parse_type()
        self._eat(TokenKind.LBRACE)

        body: list[StatementNode] = []
        while self._peek().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
                continue
            stmt = self.parse_statement()
            if self._peek().kind == TokenKind.SEMICOLON:
                self.pos += 1
            body.append(stmt)

        if not body:
            tok = self._peek()
            raise ParserError(tok.line, tok.col, "expected at least one statement in 'lore' body")

        self._eat(TokenKind.RBRACE)
        return LoreDefNode(
            line=lore_tok.line,
            col=lore_tok.col,
            name=name_tok.text,
            params=params,
            return_type=ret_type_tok.text,
            body=body,
            is_member=is_member,
        )

    def parse_type(self) -> Token:
        tok = self._peek()
        if tok.kind in (TokenKind.TYPE_NPC, TokenKind.TYPE_SIGMA, TokenKind.TYPE_TAKE, TokenKind.IDENT):
            self.pos += 1
            return tok
        raise ParserError(tok.line, tok.col, f"expected type ('npc', 'sigma', 'take' or squad name), got '{tok.text or tok.kind}'")

    def parse_statement(self) -> StatementNode:
        tok = self._peek()
        stmt: StatementNode
        match tok.kind:
            case TokenKind.CANON | TokenKind.YAP | TokenKind.CANONMAXING:
                stmt = self.parse_decl()
            case TokenKind.IDENT:
                stmt = self.parse_assign()
            case TokenKind.PRINT:
                stmt = self.parse_print()
            case TokenKind.IS_THIS_REAL:
                return self.parse_if()
            case TokenKind.EXIT:
                stmt = self.parse_exit()
            case _:
                raise ParserError(tok.line, tok.col, f"unexpected token '{tok.text or tok.kind}' at start of statement")

        if self._peek().kind == TokenKind.FR:
            fr_tok = self._eat(TokenKind.FR)
            cond = self.parse_expr()
            stmt = IfStmtNode(
                line=fr_tok.line,
                col=fr_tok.col,
                cond=cond,
                then_body=[stmt],
                else_body=None,
            )

        return stmt

    def parse_print(self) -> PrintStmtNode:
        print_tok = self._eat(TokenKind.PRINT)
        self._eat(TokenKind.LPAREN)
        arg: ExprNode
        if self._peek().kind == TokenKind.STRING:
            str_tok = self._eat(TokenKind.STRING)
            arg = StringLiteralNode(line=str_tok.line, col=str_tok.col, value=str_tok.text)
        else:
            arg = self.parse_expr()
        self._eat(TokenKind.RPAREN)
        return PrintStmtNode(line=print_tok.line, col=print_tok.col, arg=arg)

    def parse_squad_init(self) -> SquadInitNode:
        open_brace = self._eat(TokenKind.LBRACE)
        elements: list[ExprNode] = []
        if self._peek().kind != TokenKind.RBRACE:
            elem = self.parse_squad_init() if self._peek().kind == TokenKind.LBRACE else self.parse_expr()
            elements.append(elem)
            while self._peek().kind == TokenKind.COMMA:
                self.pos += 1
                elem = self.parse_squad_init() if self._peek().kind == TokenKind.LBRACE else self.parse_expr()
                elements.append(elem)
        self._eat(TokenKind.RBRACE)
        return SquadInitNode(line=open_brace.line, col=open_brace.col, elements=elements)

    def parse_decl(self) -> DeclNode:
        kind_tok = self._peek()
        self.pos += 1

        type_tok = self._peek()
        # Stage 1 compatibility check: if missing type, e.g. "canon x 👈🏻 10"
        if type_tok.kind == TokenKind.IDENT:
            next_tok = self._peek(1)
            if next_tok.kind in (TokenKind.ASSIGN, TokenKind.EMOJI_ASSIGN):
                raise ParserError(type_tok.line, type_tok.col, f"expected type ('npc', 'sigma', 'take'), got '{type_tok.text}'")
            self.pos += 1
        elif type_tok.kind in (TokenKind.TYPE_NPC, TokenKind.TYPE_SIGMA, TokenKind.TYPE_TAKE):
            self.pos += 1
        else:
            raise ParserError(type_tok.line, type_tok.col, f"expected type ('npc', 'sigma', 'take'), got '{type_tok.text or type_tok.kind}'")

        name_tok = self._eat(TokenKind.IDENT)

        assign_tok = self._peek()
        if assign_tok.kind not in (TokenKind.ASSIGN, TokenKind.EMOJI_ASSIGN):
            raise ParserError(assign_tok.line, assign_tok.col, f"expected ':=' or '👈🏻', got '{assign_tok.text or assign_tok.kind}'")
        self.pos += 1

        if self._peek().kind == TokenKind.LBRACE:
            expr: ExprNode = self.parse_squad_init()
        else:
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
        fields: list[str] = []

        while self._peek().kind == TokenKind.DOT:
            self.pos += 1
            f_tok = self._eat(TokenKind.IDENT)
            fields.append(f_tok.text)

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
            fields=fields,
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
            case TokenKind.READ:
                read_tok = self._eat(TokenKind.READ)
                self._eat(TokenKind.LPAREN)
                self._eat(TokenKind.RPAREN)
                return ReadNode(line=read_tok.line, col=read_tok.col)
            case TokenKind.IDENT:
                self.pos += 1
                id_tok = tok
                node: ExprNode
                if self._peek().kind == TokenKind.LPAREN:
                    self.pos += 1
                    args: list[ExprNode] = []
                    if self._peek().kind != TokenKind.RPAREN:
                        args.append(self.parse_expr())
                        while self._peek().kind == TokenKind.COMMA:
                            self.pos += 1
                            args.append(self.parse_expr())
                    self._eat(TokenKind.RPAREN)
                    node = CallNode(line=id_tok.line, col=id_tok.col, func_name=id_tok.text, args=args)
                else:
                    node = VarNode(line=id_tok.line, col=id_tok.col, name=id_tok.text)

                while self._peek().kind == TokenKind.DOT:
                    self.pos += 1
                    member_tok = self._eat(TokenKind.IDENT)
                    if self._peek().kind == TokenKind.LPAREN:
                        self.pos += 1
                        m_args: list[ExprNode] = []
                        if self._peek().kind != TokenKind.RPAREN:
                            m_args.append(self.parse_expr())
                            while self._peek().kind == TokenKind.COMMA:
                                self.pos += 1
                                m_args.append(self.parse_expr())
                        self._eat(TokenKind.RPAREN)
                        node = MemberCallNode(
                            line=member_tok.line,
                            col=member_tok.col,
                            target=node,
                            method_name=member_tok.text,
                            args=m_args,
                        )
                    else:
                        node = FieldAccessNode(
                            line=member_tok.line,
                            col=member_tok.col,
                            target=node,
                            field_name=member_tok.text,
                        )

                return node
            case TokenKind.LPAREN:
                self.pos += 1
                expr = self.parse_expr()
                self._eat(TokenKind.RPAREN)
                return expr
            case _:
                raise ParserError(tok.line, tok.col, f"expected expression factor (number, hot, cringe, identifier, or '('), got '{tok.text or tok.kind}'")

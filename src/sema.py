from dataclasses import dataclass, field
from src.parser import (
    ProgramNode, StmtNode, ExprNode, DeclNode, AssignNode,
    IfStmtNode, ExitStmtNode, BinOpNode, LiteralNode, VarNode,
    CallNode, FieldAccessNode, MemberCallNode, SquadDefNode,
    LoreDefNode, SquadInitNode, PrintStmtNode, ReadNode,
    StringLiteralNode, FieldDef, ParamDef
)

MAX_I32 = 2147483647
MAX_I64 = 9223372036854775807

class SemanticError(Exception):
    def __init__(self, line: int, col: int, message: str) -> None:
        self.line = line
        self.col = col
        self.message = message
        super().__init__(f"compilation error: line {line}:{col}: {message}")

@dataclass(slots=True)
class VarInfo:
    name: str
    type_name: str
    kind: str
    mutable: bool
    line: int
    col: int
    is_global: bool = False


@dataclass(slots=True)
class FieldInfo:
    index: int
    name: str
    type_name: str
    kind: str
    mutable: bool
    line: int
    col: int


@dataclass(slots=True)
class LoreInfo:
    name: str
    params: list[ParamDef]
    return_type: str
    line: int
    col: int
    is_member: bool = False
    is_mutating: bool = False
    struct_name: str | None = None
    called_methods: set[tuple[str, str]] = field(default_factory=set)


@dataclass(slots=True)
class SquadInfo:
    name: str
    line: int
    col: int
    fields: list[FieldInfo]
    fields_by_name: dict[str, FieldInfo]
    methods: dict[str, LoreInfo]


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.squads: dict[str, SquadInfo] = {}
        self.functions: dict[str, LoreInfo] = {}
        self.global_scope: dict[str, VarInfo] = {}
        self.local_scopes: list[dict[str, VarInfo]] = []
        self.current_squad: SquadInfo | None = None
        self.current_lore: LoreInfo | None = None
        self.expr_types: dict[int, str] = {}
        self.name_origins: dict[int, tuple[str, str]] = {}
        self.call_origins: dict[int, tuple[str, str | None]] = {}
        self.deferred_mutability_checks: list[tuple[str, str, int, int, str]] = []

    def set_type(self, node: ExprNode, type_name: str) -> str:
        self.expr_types[id(node)] = type_name
        return type_name

    def get_type(self, node: ExprNode) -> str:
        return self.expr_types.get(id(node), "unknown")

    def _is_valid_type(self, type_name: str) -> bool:
        return type_name in ("npc", "sigma", "take") or type_name in self.squads

    def resolve_name(self, name: str) -> tuple[str, VarInfo | FieldInfo] | None:
        """Resolve identifier following priority: 1. locals/params -> 2. squad fields -> 3. globals."""
        for scope in reversed(self.local_scopes):
            if name in scope:
                return ("local", scope[name])
        if self.current_squad is not None and name in self.current_squad.fields_by_name:
            return ("field", self.current_squad.fields_by_name[name])
        if name in self.global_scope:
            return ("global", self.global_scope[name])
        return None

    def analyze(self, prog: ProgramNode) -> None:
        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                self._collect_squad(stmt)

        for sq in self.squads.values():
            for f in sq.fields:
                if f.type_name == sq.name:
                    raise SemanticError(f.line, f.col, f"squad '{sq.name}' cannot contain a field of its own type directly")
                if not self._is_valid_type(f.type_name):
                    raise SemanticError(f.line, f.col, f"unknown type '{f.type_name}' for field '{f.name}' in squad '{sq.name}'")
            for m_info in sq.methods.values():
                if not self._is_valid_type(m_info.return_type):
                    raise SemanticError(m_info.line, m_info.col, f"unknown return type '{m_info.return_type}' in method '{m_info.name}'")

        self._check_squad_cycles()

        for stmt in prog.statements:
            if isinstance(stmt, LoreDefNode):
                self._collect_global_lore(stmt)

        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                self._check_squad_methods(stmt)
            elif isinstance(stmt, LoreDefNode):
                self._check_global_lore_body(stmt)
            else:
                self._check_stmt(stmt, is_top_level=True)

        changed = True
        while changed:
            changed = False
            for sq in self.squads.values():
                for m_info in sq.methods.values():
                    if not m_info.is_mutating:
                        for target_sq, callee_name in m_info.called_methods:
                            if self.squads[target_sq].methods[callee_name].is_mutating:
                                m_info.is_mutating = True
                                changed = True
                                break

        for sq_name, method_name, err_line, err_col, err_msg in self.deferred_mutability_checks:
            if self.squads[sq_name].methods[method_name].is_mutating:
                raise SemanticError(err_line, err_col, err_msg)

    def _check_squad_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(sq_name: str) -> None:
            visiting.add(sq_name)
            sq = self.squads[sq_name]
            for f in sq.fields:
                if f.type_name in self.squads:
                    if f.type_name in visiting:
                        raise SemanticError(f.line, f.col, f"recursive squad definition detected involving '{sq_name}' and '{f.type_name}'")
                    if f.type_name not in visited:
                        dfs(f.type_name)
            visiting.remove(sq_name)
            visited.add(sq_name)

        for name in self.squads:
            if name not in visited:
                dfs(name)

    def _collect_squad(self, node: SquadDefNode) -> None:
        if node.name in ("npc", "sigma", "take"):
            raise SemanticError(node.line, node.col, f"cannot name squad with built-in type '{node.name}'")
        if node.name in self.squads:
            raise SemanticError(node.line, node.col, f"squad '{node.name}' is already declared")

        fields: list[FieldInfo] = []
        fields_by_name: dict[str, FieldInfo] = {}
        for idx, f in enumerate(node.fields):
            if f.name in fields_by_name:
                raise SemanticError(f.line, f.col, f"field '{f.name}' is already declared in squad '{node.name}'")
            f_info = FieldInfo(
                index=idx,
                name=f.name,
                type_name=f.type_name,
                kind=f.kind,
                mutable=(f.kind == "yap"),
                line=f.line,
                col=f.col,
            )
            fields.append(f_info)
            fields_by_name[f.name] = f_info

        methods: dict[str, LoreInfo] = {}
        for m in node.methods:
            if m.name in fields_by_name:
                raise SemanticError(m.line, m.col, f"member function '{m.name}' clashes with field '{m.name}' in squad '{node.name}'")
            if m.name in methods:
                raise SemanticError(m.line, m.col, f"member function '{m.name}' is already declared in squad '{node.name}'")
            methods[m.name] = LoreInfo(
                name=m.name,
                params=m.params,
                return_type=m.return_type,
                line=m.line,
                col=m.col,
                is_member=True,
                struct_name=node.name,
            )

        self.squads[node.name] = SquadInfo(
            name=node.name,
            line=node.line,
            col=node.col,
            fields=fields,
            fields_by_name=fields_by_name,
            methods=methods,
        )

    def _collect_global_lore(self, node: LoreDefNode) -> None:
        if node.name in ("npc", "sigma", "take"):
            raise SemanticError(node.line, node.col, f"cannot name function with built-in type '{node.name}'")
        if node.name in self.functions:
            raise SemanticError(node.line, node.col, f"function '{node.name}' is already declared")
        if node.name in self.squads:
            raise SemanticError(node.line, node.col, f"function '{node.name}' clashes with squad '{node.name}'")
        if not self._is_valid_type(node.return_type):
            raise SemanticError(node.line, node.col, f"unknown return type '{node.return_type}' in function '{node.name}'")
        self.functions[node.name] = LoreInfo(
            name=node.name,
            params=node.params,
            return_type=node.return_type,
            line=node.line,
            col=node.col,
            is_member=False,
        )

    def _check_squad_methods(self, stmt: SquadDefNode) -> None:
        sq_info = self.squads[stmt.name]
        self.current_squad = sq_info
        for m_node in stmt.methods:
            m_info = sq_info.methods[m_node.name]
            self.current_lore = m_info
            self.local_scopes.append({})
            seen_params: set[str] = set()
            for p in m_node.params:
                if p.name in seen_params:
                    raise SemanticError(p.line, p.col, f"duplicate parameter name '{p.name}' in method '{m_node.name}'")
                seen_params.add(p.name)
                if not self._is_valid_type(p.type_name):
                    raise SemanticError(p.line, p.col, f"unknown parameter type '{p.type_name}' in method '{m_node.name}'")
                self.local_scopes[-1][p.name] = VarInfo(
                    name=p.name,
                    type_name=p.type_name,
                    kind="canon",
                    mutable=False,
                    line=p.line,
                    col=p.col,
                )

            has_exit = False
            for s in m_node.body:
                if self._check_stmt(s):
                    has_exit = True
            if not has_exit:
                raise SemanticError(m_node.line, m_node.col, f"member function '{m_node.name}' must leave with a value using 'exit'")

            self.local_scopes.pop()
            self.current_lore = None
        self.current_squad = None

    def _check_global_lore_body(self, stmt: LoreDefNode) -> None:
        fn_info = self.functions[stmt.name]
        self.current_lore = fn_info
        self.local_scopes.append({})
        seen_params: set[str] = set()
        for p in stmt.params:
            if p.name in seen_params:
                raise SemanticError(p.line, p.col, f"duplicate parameter name '{p.name}' in function '{stmt.name}'")
            seen_params.add(p.name)
            if not self._is_valid_type(p.type_name):
                raise SemanticError(p.line, p.col, f"unknown parameter type '{p.type_name}' in function '{stmt.name}'")
            self.local_scopes[-1][p.name] = VarInfo(
                name=p.name,
                type_name=p.type_name,
                kind="canon",
                mutable=False,
                line=p.line,
                col=p.col,
            )

        has_exit = False
        for s in stmt.body:
            if self._check_stmt(s):
                has_exit = True
        if not has_exit:
            raise SemanticError(stmt.line, stmt.col, f"function '{stmt.name}' must leave with a value using 'exit'")

        self.local_scopes.pop()
        self.current_lore = None

    def _check_stmt(self, stmt: StmtNode, is_top_level: bool = False) -> bool:
        match stmt:
            case DeclNode():
                self._check_decl(stmt, is_top_level)
                return False
            case AssignNode():
                self._check_assign(stmt)
                return False
            case PrintStmtNode():
                self._check_print(stmt)
                return False
            case IfStmtNode():
                return self._check_if(stmt)
            case ExitStmtNode():
                self._check_exit(stmt)
                return True
            case _:
                return False

    def _check_decl(self, decl: DeclNode, is_top_level: bool) -> None:
        target_scope = self.global_scope if (is_top_level and not self.local_scopes) else self.local_scopes[-1]
        if decl.name in target_scope:
            raise SemanticError(decl.line, decl.col, f"variable '{decl.name}' is already declared in this scope")

        if not self._is_valid_type(decl.type_name):
            raise SemanticError(decl.line, decl.col, f"unknown type '{decl.type_name}'")

        if isinstance(decl.expr, SquadInitNode):
            if decl.type_name not in self.squads:
                raise SemanticError(decl.line, decl.col, f"cannot initialize non-squad type '{decl.type_name}' with squad initializer")
            self._check_squad_init(decl.expr, decl.type_name)
        else:
            expr_type = self._check_expr(decl.expr, expected_type=decl.type_name)
            if expr_type != decl.type_name:
                raise SemanticError(decl.expr.line, decl.expr.col, f"cannot initialize variable of type '{decl.type_name}' with expression of type '{expr_type}'")

        is_global_var = is_top_level and not self.local_scopes
        var_info = VarInfo(
            name=decl.name,
            type_name=decl.type_name,
            kind=decl.kind,
            mutable=(decl.kind == "yap"),
            line=decl.line,
            col=decl.col,
            is_global=is_global_var,
        )
        target_scope[decl.name] = var_info
        self.name_origins[id(decl)] = ("global" if is_global_var else "local", decl.type_name)

    def _check_squad_init(self, node: SquadInitNode, sq_name: str) -> None:
        sq_info = self.squads[sq_name]
        if len(node.elements) != len(sq_info.fields):
            raise SemanticError(node.line, node.col, f"squad '{sq_name}' expects {len(sq_info.fields)} fields, got {len(node.elements)}")

        for elem, f_info in zip(node.elements, sq_info.fields):
            if isinstance(elem, SquadInitNode):
                if f_info.type_name not in self.squads:
                    raise SemanticError(elem.line, elem.col, f"field '{f_info.name}' is of type '{f_info.type_name}', not a squad")
                self._check_squad_init(elem, f_info.type_name)
            else:
                elem_type = self._check_expr(elem, expected_type=f_info.type_name)
                if elem_type != f_info.type_name:
                    raise SemanticError(elem.line, elem.col, f"field '{f_info.name}' expects type '{f_info.type_name}', got '{elem_type}'")
        self.set_type(node, sq_name)

    def _check_assign(self, assign: AssignNode) -> None:
        resolved = self.resolve_name(assign.name)
        if resolved is None:
            raise SemanticError(assign.line, assign.col, f"undefined variable '{assign.name}'")

        origin, root_info = resolved
        self.name_origins[id(assign)] = (origin, root_info.type_name)

        if not assign.fields:
            if not root_info.mutable:
                target_desc = f"field '{assign.name}'" if origin == "field" else f"variable '{assign.name}'"
                raise SemanticError(assign.line, assign.col, f"cannot assign to {root_info.kind} {target_desc}")

            expr_type = self._check_expr(assign.expr, expected_type=root_info.type_name)
            if expr_type != root_info.type_name:
                raise SemanticError(assign.expr.line, assign.expr.col, f"cannot assign expression of type '{expr_type}' to target of type '{root_info.type_name}'")

            if origin == "field" and self.current_lore:
                self.current_lore.is_mutating = True
        else:
            if not root_info.mutable:
                if origin == "field":
                    raise SemanticError(assign.line, assign.col, f"cannot assign through {root_info.kind} field '{root_info.name}'")
                raise SemanticError(assign.line, assign.col, f"cannot assign to field through {root_info.kind} variable '{root_info.name}'")

            curr_type = root_info.type_name
            for f_name in assign.fields:
                if curr_type not in self.squads:
                    raise SemanticError(assign.line, assign.col, f"type '{curr_type}' is not a squad and has no fields")
                sq = self.squads[curr_type]
                if f_name not in sq.fields_by_name:
                    raise SemanticError(assign.line, assign.col, f"squad '{curr_type}' has no field '{f_name}'")
                f_info = sq.fields_by_name[f_name]
                if not f_info.mutable:
                    raise SemanticError(assign.line, assign.col, f"cannot assign through {f_info.kind} field '{f_name}'")
                curr_type = f_info.type_name

            expr_type = self._check_expr(assign.expr, expected_type=curr_type)
            if expr_type != curr_type:
                raise SemanticError(assign.expr.line, assign.expr.col, f"cannot assign expression of type '{expr_type}' to field of type '{curr_type}'")

            if origin == "field" and self.current_lore:
                self.current_lore.is_mutating = True

    def _check_print(self, print_stmt: PrintStmtNode) -> None:
        if isinstance(print_stmt.arg, StringLiteralNode):
            self.set_type(print_stmt.arg, "string")
            return
        arg_type = self._check_expr(print_stmt.arg)
        if not self._is_valid_type(arg_type):
            raise SemanticError(print_stmt.arg.line, print_stmt.arg.col, f"cannot print value of type '{arg_type}'")

    def _check_if(self, node: IfStmtNode) -> bool:
        cond_type = self._check_expr(node.cond, expected_type="take")
        if cond_type != "take":
            raise SemanticError(node.cond.line, node.cond.col, f"if condition must be of type 'take', got '{cond_type}'")

        self.local_scopes.append({})
        then_exits = False
        for s in node.then_body:
            if self._check_stmt(s):
                then_exits = True
        self.local_scopes.pop()

        else_exits = False
        if node.else_body is not None:
            self.local_scopes.append({})
            for s in node.else_body:
                if self._check_stmt(s):
                    else_exits = True
            self.local_scopes.pop()

        return then_exits and else_exits

    def _check_exit(self, exit_stmt: ExitStmtNode) -> None:
        expected = self.current_lore.return_type if self.current_lore else None
        expr_type = self._check_expr(exit_stmt.expr, expected_type=expected)
        if self.current_lore:
            if expr_type != self.current_lore.return_type:
                raise SemanticError(
                    exit_stmt.expr.line,
                    exit_stmt.expr.col,
                    f"function '{self.current_lore.name}' return type mismatch: expected '{self.current_lore.return_type}', got '{expr_type}'",
                )

    def _check_expr(self, expr: ExprNode, expected_type: str | None = None) -> str:
        match expr:
            case LiteralNode():
                if isinstance(expr.value, bool):
                    return self.set_type(expr, "take")
                t = "sigma" if expected_type == "sigma" else "npc"
                if t == "npc" and expr.value > MAX_I32:
                    raise SemanticError(expr.line, expr.col, f"integer literal overflow: '{expr.value}' exceeds 32-bit integer range for type 'npc'")
                return self.set_type(expr, t)

            case VarNode():
                resolved = self.resolve_name(expr.name)
                if resolved is None:
                    raise SemanticError(expr.line, expr.col, f"undefined variable '{expr.name}'")
                origin, info = resolved
                self.name_origins[id(expr)] = (origin, info.type_name)
                return self.set_type(expr, info.type_name)

            case ReadNode():
                return self.set_type(expr, "npc")

            case BinOpNode():
                is_comp = expr.op in ("==", "!=", "🤝", "💔")
                op_expected = expected_type if not is_comp else None
                if isinstance(expr.left, LiteralNode) and not isinstance(expr.right, LiteralNode):
                    right_type = self._check_expr(expr.right, expected_type=op_expected)
                    left_type = self._check_expr(expr.left, expected_type=right_type)
                else:
                    left_type = self._check_expr(expr.left, expected_type=op_expected)
                    right_type = self._check_expr(expr.right, expected_type=left_type)
                    if left_type == "npc" and right_type == "sigma":
                        left_type = self._check_expr(expr.left, expected_type="sigma")

                if left_type != right_type:
                    raise SemanticError(expr.line, expr.col, f"type mismatch for operator '{expr.op}': '{left_type}' and '{right_type}'")

                if is_comp:
                    if left_type not in ("npc", "sigma", "take"):
                        raise SemanticError(expr.line, expr.col, f"cannot compare values of type '{left_type}'")
                    return self.set_type(expr, "take")
                if left_type not in ("npc", "sigma"):
                    raise SemanticError(expr.line, expr.col, f"operator '{expr.op}' not supported for type '{left_type}'")
                return self.set_type(expr, left_type)

            case CallNode():
                if self.current_squad and expr.func_name in self.current_squad.methods:
                    callee = self.current_squad.methods[expr.func_name]
                    self.call_origins[id(expr)] = ("method", self.current_squad.name)
                    if self.current_lore:
                        self.current_lore.called_methods.add((self.current_squad.name, expr.func_name))
                elif expr.func_name in self.functions:
                    callee = self.functions[expr.func_name]
                    self.call_origins[id(expr)] = ("function", None)
                else:
                    raise SemanticError(expr.line, expr.col, f"undefined function '{expr.func_name}'")

                if len(expr.args) != len(callee.params):
                    raise SemanticError(expr.line, expr.col, f"function '{callee.name}' expects {len(callee.params)} arguments, got {len(expr.args)}")

                for arg, p in zip(expr.args, callee.params):
                    a_type = self._check_expr(arg, expected_type=p.type_name)
                    if a_type != p.type_name:
                        raise SemanticError(arg.line, arg.col, f"argument type mismatch for function '{callee.name}': expected '{p.type_name}', got '{a_type}'")

                return self.set_type(expr, callee.return_type)

            case FieldAccessNode():
                target_type = self._check_expr(expr.target)
                if target_type not in self.squads:
                    raise SemanticError(expr.line, expr.col, f"type '{target_type}' is not a squad and has no fields")
                sq = self.squads[target_type]
                if expr.field_name not in sq.fields_by_name:
                    raise SemanticError(expr.line, expr.col, f"squad '{target_type}' has no field '{expr.field_name}'")
                return self.set_type(expr, sq.fields_by_name[expr.field_name].type_name)

            case MemberCallNode():
                target_type = self._check_expr(expr.target)
                if target_type not in self.squads:
                    raise SemanticError(expr.line, expr.col, f"cannot call method '{expr.method_name}' on non-squad type '{target_type}'")
                sq = self.squads[target_type]
                if expr.method_name not in sq.methods:
                    raise SemanticError(expr.line, expr.col, f"squad '{target_type}' has no method '{expr.method_name}'")
                method = sq.methods[expr.method_name]

                if len(expr.args) != len(method.params):
                    raise SemanticError(expr.line, expr.col, f"method '{method.name}' expects {len(method.params)} arguments, got {len(expr.args)}")

                for arg, p in zip(expr.args, method.params):
                    a_type = self._check_expr(arg, expected_type=p.type_name)
                    if a_type != p.type_name:
                        raise SemanticError(arg.line, arg.col, f"argument type mismatch for method '{method.name}': expected '{p.type_name}', got '{a_type}'")

                immut_err = self._find_target_immutability_error(expr.target, expr.method_name)
                if immut_err is not None:
                    err_line, err_col, err_msg = immut_err
                    if method.is_mutating:
                        raise SemanticError(err_line, err_col, err_msg)
                    self.deferred_mutability_checks.append((target_type, expr.method_name, err_line, err_col, err_msg))

                if self.current_lore and self.current_lore.is_member and self._target_root_is_this_field(expr.target):
                    self.current_lore.called_methods.add((target_type, expr.method_name))

                return self.set_type(expr, method.return_type)

            case _:
                return self.set_type(expr, "unknown")

    def _target_root_is_this_field(self, target: ExprNode) -> bool:
        curr = target
        while isinstance(curr, FieldAccessNode):
            curr = curr.target
        if isinstance(curr, VarNode):
            origin_info = self.name_origins.get(id(curr))
            return origin_info is not None and origin_info[0] == "field"
        return False

    def _find_target_immutability_error(self, target: ExprNode, method_name: str) -> tuple[int, int, str] | None:
        if isinstance(target, VarNode):
            resolved = self.resolve_name(target.name)
            if resolved is not None:
                origin, info = resolved
                if not info.mutable:
                    target_kind = "field" if origin == "field" else "variable"
                    return (target.line, target.col, f"cannot call mutating member function '{method_name}' on {info.kind} {target_kind} '{info.name}'")
        elif isinstance(target, FieldAccessNode):
            parent_err = self._find_target_immutability_error(target.target, method_name)
            if parent_err is not None:
                return parent_err
            sq_name = self.get_type(target.target)
            if sq_name in self.squads:
                f_info = self.squads[sq_name].fields_by_name.get(target.field_name)
                if f_info and not f_info.mutable:
                    return (target.line, target.col, f"cannot call mutating member function '{method_name}' through {f_info.kind} field '{target.field_name}'")
        return None


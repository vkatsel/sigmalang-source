from dataclasses import dataclass
from src.parser import (
    ProgramNode, StmtNode, ExprNode, DeclNode, AssignNode,
    IfStmtNode, WhileStmtNode, ForStmtNode, BreakStmtNode,
    ExitStmtNode, BinOpNode, LiteralNode, VarNode,
    CallNode, FieldAccessNode, MemberCallNode, SquadDefNode,
    LoreDefNode, SquadInitNode, PrintStmtNode, ReadNode,
    StringLiteralNode
)
from src.sema import SemanticAnalyzer


class EffectAnalyzer:
    def __init__(self, tree: ProgramNode) -> None:
        self.tree = tree
        self.direct_effects: set[str] = set()
        self.call_graph: dict[str, set[str]] = {}

    def _analyze_stmts(self, key: str, stmts: list[StmtNode]) -> None:
        has_direct = False
        callees: set[str] = set()

        def walk_expr(expr: ExprNode | None) -> None:
            nonlocal has_direct
            if expr is None:
                return
            match expr:
                case ReadNode():
                    has_direct = True
                case CallNode(func_name=fn, args=args):
                    callees.add(f"fn:{fn}")
                    for a in args:
                        walk_expr(a)
                case MemberCallNode(target=t, method_name=mn, args=args):
                    has_direct = True
                    walk_expr(t)
                    for a in args:
                        walk_expr(a)
                case BinOpNode(left=l, right=r):
                    walk_expr(l)
                    walk_expr(r)
                case FieldAccessNode(target=t):
                    walk_expr(t)
                case SquadInitNode(elements=elems):
                    for e in elems:
                        walk_expr(e)
                case _:
                    pass

        def walk_stmt(stmt: StmtNode | None) -> None:
            nonlocal has_direct
            if stmt is None:
                return
            match stmt:
                case PrintStmtNode(arg=a):
                    has_direct = True
                    walk_expr(a)
                case WhileStmtNode(cond=c, body=b):
                    has_direct = True
                    walk_expr(c)
                    for s in b:
                        walk_stmt(s)
                case ForStmtNode(start=st, end=en, body=b):
                    has_direct = True
                    walk_expr(st)
                    walk_expr(en)
                    for s in b:
                        walk_stmt(s)
                case IfStmtNode(cond=c, then_body=tb, else_body=eb):
                    walk_expr(c)
                    for s in tb:
                        walk_stmt(s)
                    if eb is not None:
                        for s in eb:
                            walk_stmt(s)
                case DeclNode(expr=e):
                    walk_expr(e)
                case AssignNode(expr=e, fields=f):
                    if f:
                        has_direct = True
                    walk_expr(e)
                case ExitStmtNode(expr=e):
                    walk_expr(e)
                case BreakStmtNode():
                    pass
                case _:
                    pass

        for s in stmts:
            walk_stmt(s)

        if has_direct:
            self.direct_effects.add(key)
        self.call_graph[key] = callees

    def compute_effects(self) -> set[str]:
        all_keys: list[str] = []
        for stmt in self.tree.statements:
            if isinstance(stmt, LoreDefNode):
                key = f"fn:{stmt.name}"
                all_keys.append(key)
                self._analyze_stmts(key, stmt.body)
            elif isinstance(stmt, SquadDefNode):
                for m in stmt.methods:
                    key = f"mfn:{stmt.name}:{m.name}"
                    all_keys.append(key)
                    self._analyze_stmts(key, m.body)

        effects: set[str] = set(self.direct_effects)

        # Detect recursion / cycles in call graph
        for start_k in all_keys:
            if start_k in effects:
                continue
            visited: set[str] = set()
            stack = list(self.call_graph.get(start_k, set()))
            while stack:
                curr = stack.pop()
                if curr == start_k:
                    effects.add(start_k)
                    break
                if curr not in visited:
                    visited.add(curr)
                    stack.extend(self.call_graph.get(curr, set()))

        # Fixpoint propagation
        changed = True
        while changed:
            changed = False
            for caller, callees in self.call_graph.items():
                if caller not in effects:
                    if any(c in effects for c in callees):
                        effects.add(caller)
                        changed = True

        return effects


def has_effect(expr: ExprNode | None, effects: set[str]) -> bool:
    if expr is None:
        return False
    match expr:
        case ReadNode():
            return True
        case CallNode(func_name=fn, args=args):
            return f"fn:{fn}" in effects or any(has_effect(a, effects) for a in args)
        case MemberCallNode(target=t, args=args):
            return True or has_effect(t, effects) or any(has_effect(a, effects) for a in args)
        case BinOpNode(left=l, right=r):
            return has_effect(l, effects) or has_effect(r, effects)
        case FieldAccessNode(target=t):
            return has_effect(t, effects)
        case SquadInitNode(elements=elems):
            return any(has_effect(e, effects) for e in elems)
        case _:
            return False


class UseCounter:
    def __init__(self, sema: SemanticAnalyzer, effects: set[str]) -> None:
        self.sema = sema
        self.effects = effects
        self.reads: dict[int, int] = {}
        self.fn_calls: dict[str, int] = {}

    def count(self, tree: ProgramNode) -> None:
        # Pre-seed all global LoreDefNode in fn_calls
        for s in tree.statements:
            if isinstance(s, LoreDefNode):
                self.fn_calls.setdefault(s.name, 0)

        # Pre-seed all DeclNode in reads
        def register_decls(stmts: list[StmtNode]) -> None:
            for s in stmts:
                match s:
                    case DeclNode():
                        self.reads.setdefault(id(s), 0)
                        register_decls_in_expr(s.expr)
                    case IfStmtNode(then_body=tb, else_body=eb):
                        register_decls(tb)
                        if eb:
                            register_decls(eb)
                    case WhileStmtNode(body=b):
                        register_decls(b)
                    case ForStmtNode(body=b):
                        register_decls(b)
                    case LoreDefNode(body=b):
                        register_decls(b)
                    case SquadDefNode(methods=ms):
                        for m in ms:
                            register_decls(m.body)
                    case _:
                        pass

        def register_decls_in_expr(expr: ExprNode) -> None:
            pass

        register_decls(tree.statements)

        # Count reads and calls
        def walk_expr(expr: ExprNode | None) -> None:
            if expr is None:
                return
            match expr:
                case VarNode():
                    decl = self.sema.decl_bindings.get(id(expr))
                    if decl is not None:
                        self.reads[id(decl)] = self.reads.get(id(decl), 0) + 1
                case CallNode(func_name=fn, args=args):
                    self.fn_calls[fn] = self.fn_calls.get(fn, 0) + 1
                    for a in args:
                        walk_expr(a)
                case MemberCallNode(target=t, args=args):
                    walk_expr(t)
                    for a in args:
                        walk_expr(a)
                case BinOpNode(left=l, right=r):
                    walk_expr(l)
                    walk_expr(r)
                case FieldAccessNode(target=t):
                    walk_expr(t)
                case SquadInitNode(elements=elems):
                    for e in elems:
                        walk_expr(e)
                case _:
                    pass

        def walk_stmt(stmt: StmtNode) -> None:
            match stmt:
                case DeclNode(expr=e):
                    walk_expr(e)
                    if has_effect(e, self.effects):
                        self.reads[id(stmt)] = self.reads.get(id(stmt), 0) + 1
                case AssignNode(expr=e, fields=f):
                    walk_expr(e)
                    if f or has_effect(e, self.effects):
                        decl = self.sema.decl_bindings.get(id(stmt))
                        if decl is not None:
                            self.reads[id(decl)] = self.reads.get(id(decl), 0) + 1
                case PrintStmtNode(arg=a):
                    walk_expr(a)
                case ExitStmtNode(expr=e):
                    walk_expr(e)
                case IfStmtNode(cond=c, then_body=tb, else_body=eb):
                    walk_expr(c)
                    for s in tb:
                        walk_stmt(s)
                    if eb is not None:
                        for s in eb:
                            walk_stmt(s)
                case WhileStmtNode(cond=c, body=b):
                    walk_expr(c)
                    for s in b:
                        walk_stmt(s)
                case ForStmtNode(start=st, end=en, body=b):
                    walk_expr(st)
                    walk_expr(en)
                    for s in b:
                        walk_stmt(s)
                case LoreDefNode(body=b):
                    for s in b:
                        walk_stmt(s)
                case SquadDefNode(methods=ms):
                    for m in ms:
                        for s in m.body:
                            walk_stmt(s)
                case BreakStmtNode():
                    pass

        for s in tree.statements:
            walk_stmt(s)


class Pruner:
    def __init__(self, sema: SemanticAnalyzer, dead_vars: set[int], dead_fns: set[str]) -> None:
        self.sema = sema
        self.dead_vars = dead_vars
        self.dead_fns = dead_fns

    def prune_stmts(self, stmts: list[StmtNode]) -> list[StmtNode]:
        kept: list[StmtNode] = []
        for s in stmts:
            match s:
                case DeclNode() if id(s) in self.dead_vars:
                    continue
                case AssignNode() if not s.fields and (id(s) in self.sema.decl_bindings and id(self.sema.decl_bindings[id(s)]) in self.dead_vars):
                    continue
                case LoreDefNode() if s.name in self.dead_fns:
                    continue
                case IfStmtNode(then_body=tb, else_body=eb):
                    s.then_body = self.prune_stmts(tb)
                    if eb is not None:
                        s.else_body = self.prune_stmts(eb)
                case WhileStmtNode(body=b):
                    s.body = self.prune_stmts(b)
                case ForStmtNode(body=b):
                    s.body = self.prune_stmts(b)
                case LoreDefNode(body=b):
                    s.body = self.prune_stmts(b)
                case SquadDefNode(methods=ms):
                    for m in ms:
                        m.body = self.prune_stmts(m.body)
                case _:
                    pass
            kept.append(s)
        return kept

    def prune(self, tree: ProgramNode) -> ProgramNode:
        tree.statements = self.prune_stmts(tree.statements)
        return tree


def clone_and_rename_expr(expr: ExprNode, rename_map: dict[str, str]) -> ExprNode:
    match expr:
        case VarNode(line=l, col=c, name=n):
            new_name = rename_map.get(n, n)
            return VarNode(line=l, col=c, name=new_name)
        case BinOpNode(line=l, col=c, op=op, left=left, right=right):
            return BinOpNode(
                line=l,
                col=c,
                op=op,
                left=clone_and_rename_expr(left, rename_map),
                right=clone_and_rename_expr(right, rename_map),
            )
        case CallNode(line=l, col=c, func_name=fn, args=args):
            return CallNode(
                line=l,
                col=c,
                func_name=fn,
                args=[clone_and_rename_expr(a, rename_map) for a in args],
            )
        case MemberCallNode(line=l, col=c, target=t, method_name=mn, args=args):
            return MemberCallNode(
                line=l,
                col=c,
                target=clone_and_rename_expr(t, rename_map),
                method_name=mn,
                args=[clone_and_rename_expr(a, rename_map) for a in args],
            )
        case FieldAccessNode(line=l, col=c, target=t, field_name=fn):
            return FieldAccessNode(
                line=l,
                col=c,
                target=clone_and_rename_expr(t, rename_map),
                field_name=fn,
            )
        case SquadInitNode(line=l, col=c, elements=elems):
            return SquadInitNode(
                line=l,
                col=c,
                elements=[clone_and_rename_expr(e, rename_map) for e in elems],
            )
        case LiteralNode() | ReadNode() | StringLiteralNode():
            return expr
        case _:
            return expr


def clone_and_rename_stmt(stmt: StmtNode, rename_map: dict[str, str]) -> StmtNode:
    match stmt:
        case DeclNode(line=l, col=c, kind=k, type_name=tn, name=n, expr=e):
            new_name = rename_map.get(n, n)
            return DeclNode(
                line=l,
                col=c,
                kind=k,
                type_name=tn,
                name=new_name,
                expr=clone_and_rename_expr(e, rename_map),
            )
        case AssignNode(line=l, col=c, name=n, op=op, expr=e, fields=f):
            new_name = rename_map.get(n, n)
            return AssignNode(
                line=l,
                col=c,
                name=new_name,
                op=op,
                expr=clone_and_rename_expr(e, rename_map),
                fields=list(f),
            )
        case PrintStmtNode(line=l, col=c, arg=a):
            return PrintStmtNode(
                line=l,
                col=c,
                arg=clone_and_rename_expr(a, rename_map),
            )
        case ExitStmtNode(line=l, col=c, expr=e):
            return ExitStmtNode(
                line=l,
                col=c,
                expr=clone_and_rename_expr(e, rename_map),
            )
        case IfStmtNode(line=l, col=c, cond=cond, then_body=tb, else_body=eb):
            new_tb = [clone_and_rename_stmt(s, rename_map) for s in tb]
            new_eb = [clone_and_rename_stmt(s, rename_map) for s in eb] if eb else None
            return IfStmtNode(
                line=l,
                col=c,
                cond=clone_and_rename_expr(cond, rename_map),
                then_body=new_tb,
                else_body=new_eb,
            )
        case WhileStmtNode(line=l, col=c, cond=cond, body=b):
            return WhileStmtNode(
                line=l,
                col=c,
                cond=clone_and_rename_expr(cond, rename_map),
                body=[clone_and_rename_stmt(s, rename_map) for s in b],
            )
        case ForStmtNode(line=l, col=c, var_name=vn, start=st, end=en, body=b, var_type=vt):
            new_vn = rename_map.get(vn, vn)
            return ForStmtNode(
                line=l,
                col=c,
                var_name=new_vn,
                start=clone_and_rename_expr(st, rename_map),
                end=clone_and_rename_expr(en, rename_map),
                body=[clone_and_rename_stmt(s, rename_map) for s in b],
                var_type=vt,
            )
        case BreakStmtNode():
            return stmt
        case _:
            return stmt


class Inliner:
    def __init__(self, sema: SemanticAnalyzer, effects: set[str], call_graph: dict[str, set[str]], fn_calls: dict[str, int]) -> None:
        self.sema = sema
        self.effects = effects
        self.call_graph = call_graph
        self.fn_calls = fn_calls
        self.inline_counter = 0

    def _is_recursive(self, fn_name: str) -> bool:
        start_k = f"fn:{fn_name}"
        visited: set[str] = set()
        stack = list(self.call_graph.get(start_k, set()))
        while stack:
            curr = stack.pop()
            if curr == start_k:
                return True
            if curr not in visited:
                visited.add(curr)
                stack.extend(self.call_graph.get(curr, set()))
        return False

    def _can_inline(self, fn: LoreDefNode) -> bool:
        if self.fn_calls.get(fn.name, 0) != 1:
            return False
        if fn.is_member:
            return False
        if self._is_recursive(fn.name):
            return False
        if not fn.body or not isinstance(fn.body[-1], ExitStmtNode):
            return False
        # Do not inline if exit appears inside any nested statements (like if)
        for s in fn.body[:-1]:
            if self._has_exit(s):
                return False
        return True

    def _has_exit(self, stmt: StmtNode) -> bool:
        match stmt:
            case ExitStmtNode():
                return True
            case IfStmtNode(then_body=tb, else_body=eb):
                if any(self._has_exit(s) for s in tb):
                    return True
                if eb and any(self._has_exit(s) for s in eb):
                    return True
            case WhileStmtNode(body=b) | ForStmtNode(body=b):
                if any(self._has_exit(s) for s in b):
                    return True
            case _:
                pass
        return False

    def try_inline_once(self, tree: ProgramNode) -> bool:
        fn_map: dict[str, LoreDefNode] = {}
        for s in tree.statements:
            if isinstance(s, LoreDefNode):
                fn_map[s.name] = s

        inline_target: LoreDefNode | None = None
        for fn in fn_map.values():
            if self._can_inline(fn):
                inline_target = fn
                break

        if inline_target is None:
            return False

        target_fn_name = inline_target.name

        def replace_call_in_expr(expr: ExprNode) -> tuple[ExprNode, CallNode | None]:
            match expr:
                case CallNode(func_name=fn) if fn == target_fn_name:
                    return expr, expr
                case BinOpNode(line=l, col=c, op=op, left=left, right=right):
                    new_l, c_l = replace_call_in_expr(left)
                    if c_l is not None:
                        return BinOpNode(line=l, col=c, op=op, left=new_l, right=right), c_l
                    new_r, c_r = replace_call_in_expr(right)
                    return BinOpNode(line=l, col=c, op=op, left=left, right=new_r), c_r
                case PrintStmtNode(line=l, col=c, arg=a):
                    new_a, c_a = replace_call_in_expr(a)
                    return PrintStmtNode(line=l, col=c, arg=new_a), c_a
                case FieldAccessNode(line=l, col=c, target=t, field_name=fn):
                    new_t, c_t = replace_call_in_expr(t)
                    return FieldAccessNode(line=l, col=c, target=new_t, field_name=fn), c_t
                case SquadInitNode(line=l, col=c, elements=elems):
                    new_elems: list[ExprNode] = []
                    found_call = None
                    for e in elems:
                        if found_call is None:
                            new_e, c_e = replace_call_in_expr(e)
                            new_elems.append(new_e)
                            if c_e is not None:
                                found_call = c_e
                        else:
                            new_elems.append(e)
                    return SquadInitNode(line=l, col=c, elements=new_elems), found_call
                case _:
                    return expr, None

        def inline_in_stmts(stmts: list[StmtNode]) -> tuple[list[StmtNode], bool]:
            new_stmts: list[StmtNode] = []
            inlined = False
            for s in stmts:
                if inlined:
                    new_stmts.append(s)
                    continue

                call_found: CallNode | None = None
                new_stmt = s

                match s:
                    case DeclNode(line=l, col=c, kind=k, type_name=tn, name=n, expr=e):
                        new_e, c_e = replace_call_in_expr(e)
                        if c_e is not None:
                            call_found = c_e
                            new_stmt = DeclNode(line=l, col=c, kind=k, type_name=tn, name=n, expr=new_e)
                    case AssignNode(line=l, col=c, name=n, op=op, expr=e, fields=f):
                        new_e, c_e = replace_call_in_expr(e)
                        if c_e is not None:
                            call_found = c_e
                            new_stmt = AssignNode(line=l, col=c, name=n, op=op, expr=new_e, fields=f)
                    case PrintStmtNode(line=l, col=c, arg=a):
                        new_a, c_a = replace_call_in_expr(a)
                        if c_a is not None:
                            call_found = c_a
                            new_stmt = PrintStmtNode(line=l, col=c, arg=new_a)
                    case ExitStmtNode(line=l, col=c, expr=e):
                        new_e, c_e = replace_call_in_expr(e)
                        if c_e is not None:
                            call_found = c_e
                            new_stmt = ExitStmtNode(line=l, col=c, expr=new_e)
                    case IfStmtNode(line=l, col=c, cond=cond, then_body=tb, else_body=eb):
                        new_cond, c_cond = replace_call_in_expr(cond)
                        if c_cond is not None:
                            call_found = c_cond
                            new_stmt = IfStmtNode(line=l, col=c, cond=new_cond, then_body=tb, else_body=eb)
                        else:
                            new_tb, inlined_tb = inline_in_stmts(tb)
                            if inlined_tb:
                                new_stmts.append(IfStmtNode(line=l, col=c, cond=cond, then_body=new_tb, else_body=eb))
                                inlined = True
                                continue
                            if eb:
                                new_eb, inlined_eb = inline_in_stmts(eb)
                                if inlined_eb:
                                    new_stmts.append(IfStmtNode(line=l, col=c, cond=cond, then_body=tb, else_body=new_eb))
                                    inlined = True
                                    continue
                    case WhileStmtNode(line=l, col=c, cond=cond, body=b):
                        new_cond, c_cond = replace_call_in_expr(cond)
                        if c_cond is not None:
                            call_found = c_cond
                            new_stmt = WhileStmtNode(line=l, col=c, cond=new_cond, body=b)
                        else:
                            new_b, inlined_b = inline_in_stmts(b)
                            if inlined_b:
                                new_stmts.append(WhileStmtNode(line=l, col=c, cond=cond, body=new_b))
                                inlined = True
                                continue
                    case ForStmtNode(line=l, col=c, var_name=vn, start=st, end=en, body=b, var_type=vt):
                        new_st, c_st = replace_call_in_expr(st)
                        if c_st is not None:
                            call_found = c_st
                            new_stmt = ForStmtNode(line=l, col=c, var_name=vn, start=new_st, end=en, body=b, var_type=vt)
                        else:
                            new_b, inlined_b = inline_in_stmts(b)
                            if inlined_b:
                                new_stmts.append(ForStmtNode(line=l, col=c, var_name=vn, start=st, end=en, body=new_b, var_type=vt))
                                inlined = True
                                continue
                    case LoreDefNode(body=b):
                        new_b, inlined_b = inline_in_stmts(b)
                        if inlined_b:
                            s.body = new_b
                            new_stmts.append(s)
                            inlined = True
                            continue
                    case SquadDefNode(methods=ms):
                        for m in ms:
                            new_b, inlined_b = inline_in_stmts(m.body)
                            if inlined_b:
                                m.body = new_b
                                inlined = True
                                break
                        new_stmts.append(s)
                        if inlined:
                            continue
                    case _:
                        pass

                if call_found is not None:
                    self.inline_counter += 1
                    prefix = f"_inl_{self.inline_counter}_"
                    rename_map: dict[str, str] = {}
                    injected_stmts: list[StmtNode] = []

                    # 1. Bind parameters to argument values
                    for p, arg in zip(inline_target.params, call_found.args):
                        renamed_p = f"{prefix}{p.name}"
                        rename_map[p.name] = renamed_p
                        injected_stmts.append(
                            DeclNode(
                                line=p.line,
                                col=p.col,
                                kind="canon",
                                type_name=p.type_name,
                                name=renamed_p,
                                expr=arg,
                            )
                        )

                    # 2. Collect local declarations to alpha-rename
                    for body_stmt in inline_target.body[:-1]:
                        if isinstance(body_stmt, DeclNode):
                            rename_map[body_stmt.name] = f"{prefix}{body_stmt.name}"

                    # 3. Clone and rename statements before exit
                    for body_stmt in inline_target.body[:-1]:
                        injected_stmts.append(clone_and_rename_stmt(body_stmt, rename_map))

                    # 4. Clone and rename the return expression
                    exit_stmt = inline_target.body[-1]
                    assert isinstance(exit_stmt, ExitStmtNode)
                    inlined_exit_val = clone_and_rename_expr(exit_stmt.expr, rename_map)

                    # Replace the CallNode in new_stmt with inlined_exit_val
                    def replace_node_ref(expr: ExprNode) -> ExprNode:
                        if expr is call_found:
                            return inlined_exit_val
                        match expr:
                            case BinOpNode(line=l, col=c, op=op, left=left, right=right):
                                return BinOpNode(line=l, col=c, op=op, left=replace_node_ref(left), right=replace_node_ref(right))
                            case FieldAccessNode(line=l, col=c, target=t, field_name=fn):
                                return FieldAccessNode(line=l, col=c, target=replace_node_ref(t), field_name=fn)
                            case SquadInitNode(line=l, col=c, elements=elems):
                                return SquadInitNode(line=l, col=c, elements=[replace_node_ref(e) for e in elems])
                            case _:
                                return expr

                    match new_stmt:
                        case DeclNode(expr=e):
                            new_stmt.expr = replace_node_ref(e)
                        case AssignNode(expr=e):
                            new_stmt.expr = replace_node_ref(e)
                        case PrintStmtNode(arg=a):
                            new_stmt.arg = replace_node_ref(a)
                        case ExitStmtNode(expr=e):
                            new_stmt.expr = replace_node_ref(e)
                        case IfStmtNode(cond=c):
                            new_stmt.cond = replace_node_ref(c)
                        case WhileStmtNode(cond=c):
                            new_stmt.cond = replace_node_ref(c)
                        case ForStmtNode(start=st):
                            new_stmt.start = replace_node_ref(st)

                    new_stmts.extend(injected_stmts)
                    new_stmts.append(new_stmt)
                    inlined = True
                else:
                    new_stmts.append(new_stmt)

            return new_stmts, inlined

        tree.statements, was_inlined = inline_in_stmts(tree.statements)
        return was_inlined


class ASTOptimizer:
    def optimize(self, tree: ProgramNode, sema: SemanticAnalyzer) -> ProgramNode:
        # Step 1: Inlining pass (inline single-use non-recursive functions)
        while True:
            effects = EffectAnalyzer(tree).compute_effects()
            counter = UseCounter(sema, effects)
            counter.count(tree)
            inliner = Inliner(sema, effects, EffectAnalyzer(tree).call_graph, counter.fn_calls)
            inlined = inliner.try_inline_once(tree)
            if not inlined:
                break
            sema.analyze(tree)

        # Step 2: Unused variables and functions elimination to fixpoint
        while True:
            effects = EffectAnalyzer(tree).compute_effects()
            counter = UseCounter(sema, effects)
            counter.count(tree)
            dead_vars = {decl_id for decl_id, count in counter.reads.items() if count == 0}
            dead_fns = {fn_name for fn_name, count in counter.fn_calls.items() if count == 0}
            if not dead_vars and not dead_fns:
                break
            pruner = Pruner(sema, dead_vars, dead_fns)
            tree = pruner.prune(tree)
            sema.analyze(tree)

        return tree

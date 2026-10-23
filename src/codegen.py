import sys
from pathlib import Path

for _p in (
    "/home/ubuntu/lcd/lib/python3.12/site-packages",
    str(Path.home() / "lcd/lib/python3.12/site-packages"),
):
    if _p not in sys.path and Path(_p).exists():
        sys.path.insert(0, _p)

from llvmlite import ir
import llvmlite.binding as llvm

from src.parser import (
    ProgramNode, StmtNode, ExprNode, DeclNode, AssignNode,
    IfStmtNode, ExitStmtNode, BinOpNode, LiteralNode, VarNode,
    CallNode, FieldAccessNode, MemberCallNode, SquadDefNode,
    LoreDefNode, SquadInitNode, PrintStmtNode, ReadNode,
    StringLiteralNode
)
from src.sema import SemanticAnalyzer


class LLVMCodeGenerator:
    def __init__(self, sema: SemanticAnalyzer) -> None:
        self.sema = sema
        self.module = ir.Module(name="sigmalang_module")
        try:
            self.module.triple = llvm.get_default_triple()
        except Exception:
            self.module.triple = "x86_64-unknown-linux-gnu"
        self.i64_type = ir.IntType(64)
        self.i32_type = ir.IntType(32)
        self.i1_type = ir.IntType(1)
        self.i8_type = ir.IntType(8)
        self.i8p_type = ir.PointerType(self.i8_type)

        self.struct_types: dict[str, ir.IdentifiedStructType] = {}
        self.fn_map: dict[str, ir.Function] = {}
        self.global_vars: dict[str, ir.GlobalVariable] = {}
        self.cached_strings: dict[str, ir.GlobalVariable] = {}
        self.var_scopes: list[dict[str, ir.Value]] = []

        self.builder: ir.IRBuilder | None = None
        self.function: ir.Function | None = None
        self.current_this: ir.Value | None = None
        self.current_lore: LoreDefNode | None = None
        self.current_squad_name: str | None = None

        c_var_fn = ir.FunctionType(self.i32_type, [self.i8p_type], var_arg=True)
        self.printf_fn = ir.Function(self.module, c_var_fn, name="printf")
        self.scanf_fn = ir.Function(self.module, c_var_fn, name="scanf")

        self.fmt_d_nl = self._create_global_string("fmt_d_nl", b"%d\n\0")
        self.fmt_lld_nl = self._create_global_string("fmt_lld_nl", b"%lld\n\0")
        self.fmt_s_nl = self._create_global_string("fmt_s_nl", b"%s\n\0")
        self.fmt_d = self._create_global_string("fmt_d", b"%d\0")
        self.fmt_lld = self._create_global_string("fmt_lld", b"%lld\0")
        self.fmt_s = self._create_global_string("fmt_s", b"%s\0")

        self.fmt_exit_int = self._create_global_string("fmt_exit_int", b"Program exit with result %lld\n\0")
        self.fmt_exit_bool = self._create_global_string("fmt_exit_bool", b"Program exit with result %s\n\0")

        self.str_true = self._create_global_string("str_true", b"true\0")
        self.str_false = self._create_global_string("str_false", b"false\0")

    def _create_global_string(self, name: str, data: bytes) -> ir.GlobalVariable:
        arr_t = ir.ArrayType(self.i8_type, len(data))
        var = ir.GlobalVariable(self.module, arr_t, name=name)
        var.linkage = "private"
        var.global_constant = True
        var.initializer = ir.Constant(arr_t, bytearray(data))
        return var

    def _get_cached_string(self, text: str) -> ir.GlobalVariable:
        if text not in self.cached_strings:
            data = text.encode("utf-8") + b"\0"
            idx = len(self.cached_strings)
            var = self._create_global_string(f"str_cache_{idx}", data)
            self.cached_strings[text] = var
        return self.cached_strings[text]

    def _llvm_type(self, type_name: str) -> ir.Type:
        match type_name:
            case "npc":
                return self.i32_type
            case "sigma":
                return self.i64_type
            case "take":
                return self.i1_type
            case _ if type_name in self.struct_types:
                return self.struct_types[type_name]
            case _:
                return self.i32_type

    def _entry_alloca(self, llvm_type: ir.Type, name: str) -> ir.AllocaInstr:
        with self.builder.goto_entry_block():
            return self.builder.alloca(llvm_type, name=name)

    def generate(self, prog: ProgramNode) -> ir.Module:
        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                st = self.module.context.get_identified_type(stmt.name)
                self.struct_types[stmt.name] = st

        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                st = self.struct_types[stmt.name]
                field_types = [self._llvm_type(f.type_name) for f in stmt.fields]
                st.set_body(*field_types)

        for stmt in prog.statements:
            if isinstance(stmt, DeclNode):
                t = self._llvm_type(stmt.type_name)
                gvar = ir.GlobalVariable(self.module, t, name=f"_global_{stmt.name}")
                gvar.linkage = "internal"
                gvar.initializer = ir.Constant(t, None)
                self.global_vars[stmt.name] = gvar

        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                st_ptr_type = ir.PointerType(self.struct_types[stmt.name])
                for m in stmt.methods:
                    fn_name = f"_squad_{stmt.name}_{m.name}"
                    param_types = [st_ptr_type] + [self._llvm_type(p.type_name) for p in m.params]
                    ret_type = self._llvm_type(m.return_type)
                    fn_type = ir.FunctionType(ret_type, param_types)
                    self.fn_map[fn_name] = ir.Function(self.module, fn_type, name=fn_name)

        for stmt in prog.statements:
            if isinstance(stmt, LoreDefNode):
                fn_name = f"_lore_{stmt.name}"
                param_types = [self._llvm_type(p.type_name) for p in stmt.params]
                ret_type = self._llvm_type(stmt.return_type)
                fn_type = ir.FunctionType(ret_type, param_types)
                self.fn_map[fn_name] = ir.Function(self.module, fn_type, name=fn_name)

        for stmt in prog.statements:
            if isinstance(stmt, SquadDefNode):
                for m in stmt.methods:
                    self._generate_member_lore(stmt.name, m)

        for stmt in prog.statements:
            if isinstance(stmt, LoreDefNode):
                self._generate_global_lore(stmt)

        main_type = ir.FunctionType(self.i32_type, [])
        main_fn = ir.Function(self.module, main_type, name="main")
        self.function = main_fn
        entry_bb = main_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(entry_bb)
        self.current_this = None
        self.current_lore = None
        self.current_squad_name = None

        for stmt in prog.statements:
            if not isinstance(stmt, (SquadDefNode, LoreDefNode)):
                self._emit_stmt(stmt)

        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.i32_type, 0))

        return self.module

    def lookup_local_slot(self, name: str) -> ir.Value | None:
        for scope in reversed(self.var_scopes):
            if name in scope:
                return scope[name]
        return None

    def _resolve_node_ptr(self, node: VarNode | AssignNode) -> ir.Value:
        origin, _ = self.sema.name_origins[id(node)]
        match origin:
            case "local":
                slot = self.lookup_local_slot(node.name)
                if slot is not None:
                    return slot
            case "field":
                if self.current_this is not None and self.current_squad_name is not None:
                    sq_info = self.sema.squads[self.current_squad_name]
                    f_info = sq_info.fields_by_name[node.name]
                    return self.builder.gep(
                        self.current_this,
                        [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, f_info.index)],
                        inbounds=True,
                        name=f"{node.name}_gep",
                    )
            case "global":
                if node.name in self.global_vars:
                    return self.global_vars[node.name]
        raise RuntimeError(f"Cannot resolve pointer for '{node.name}' (origin={origin})")

    def _generate_member_lore(self, squad_name: str, node: LoreDefNode) -> None:
        fn_name = f"_squad_{squad_name}_{node.name}"
        llvm_fn = self.fn_map[fn_name]
        self.function = llvm_fn
        entry_bb = llvm_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(entry_bb)
        self.current_lore = node
        self.current_squad_name = squad_name

        this_val = llvm_fn.args[0]
        this_val.name = "this"
        self.current_this = this_val

        self.var_scopes.append({})
        for p, arg in zip(node.params, llvm_fn.args[1:]):
            arg.name = p.name
            slot = self._entry_alloca(arg.type, name=f"{p.name}_slot")
            self.builder.store(arg, slot)
            self.var_scopes[-1][p.name] = slot

        for s in node.body:
            self._emit_stmt(s)

        if not self.builder.block.is_terminated:
            ret_t = self._llvm_type(node.return_type)
            self.builder.ret(ir.Constant(ret_t, None))

        self.var_scopes.pop()
        self.current_this = None
        self.current_lore = None
        self.current_squad_name = None

    def _generate_global_lore(self, node: LoreDefNode) -> None:
        fn_name = f"_lore_{node.name}"
        llvm_fn = self.fn_map[fn_name]
        self.function = llvm_fn
        entry_bb = llvm_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(entry_bb)
        self.current_this = None
        self.current_squad_name = None
        self.current_lore = node

        self.var_scopes.append({})
        for p, arg in zip(node.params, llvm_fn.args):
            arg.name = p.name
            slot = self._entry_alloca(arg.type, name=f"{p.name}_slot")
            self.builder.store(arg, slot)
            self.var_scopes[-1][p.name] = slot

        for s in node.body:
            self._emit_stmt(s)

        if not self.builder.block.is_terminated:
            ret_t = self._llvm_type(node.return_type)
            self.builder.ret(ir.Constant(ret_t, None))

        self.var_scopes.pop()
        self.current_lore = None

    def _emit_stmt(self, stmt: StmtNode) -> None:
        if self.builder.block.is_terminated:
            return

        match stmt:
            case DeclNode():
                origin, _ = self.sema.name_origins[id(stmt)]
                if origin == "global":
                    slot = self.global_vars[stmt.name]
                else:
                    t = self._llvm_type(stmt.type_name)
                    slot = self._entry_alloca(t, name=stmt.name)
                    self.var_scopes[-1][stmt.name] = slot

                if isinstance(stmt.expr, SquadInitNode):
                    self._emit_squad_init(slot, stmt.type_name, stmt.expr)
                else:
                    val = self._emit_expr(stmt.expr)
                    self.builder.store(val, slot)

            case AssignNode():
                val = self._emit_expr(stmt.expr)
                target_ptr = self._resolve_node_ptr(stmt)
                if not stmt.fields:
                    self.builder.store(val, target_ptr)
                else:
                    _, curr_type = self.sema.name_origins[id(stmt)]
                    for f_name in stmt.fields:
                        sq_info = self.sema.squads[curr_type]
                        f_info = sq_info.fields_by_name[f_name]
                        target_ptr = self.builder.gep(
                            target_ptr,
                            [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, f_info.index)],
                            inbounds=True,
                            name=f"{f_name}_gep",
                        )
                        curr_type = f_info.type_name
                    self.builder.store(val, target_ptr)

            case PrintStmtNode():
                self._emit_print(stmt.arg)

            case IfStmtNode():
                cond_val = self._emit_expr(stmt.cond)
                then_bb = self.function.append_basic_block("then")
                else_bb = self.function.append_basic_block("else") if stmt.else_body is not None else None
                merge_bb = self.function.append_basic_block("merge")

                self.builder.cbranch(cond_val, then_bb, else_bb if else_bb is not None else merge_bb)

                self.builder.position_at_end(then_bb)
                self.var_scopes.append({})
                for s in stmt.then_body:
                    self._emit_stmt(s)
                self.var_scopes.pop()
                if not self.builder.block.is_terminated:
                    self.builder.branch(merge_bb)

                if stmt.else_body is not None and else_bb is not None:
                    self.builder.position_at_end(else_bb)
                    self.var_scopes.append({})
                    for s in stmt.else_body:
                        self._emit_stmt(s)
                    self.var_scopes.pop()
                    if not self.builder.block.is_terminated:
                        self.builder.branch(merge_bb)

                self.builder.position_at_end(merge_bb)

            case ExitStmtNode():
                val = self._emit_expr(stmt.expr)
                if self.current_lore:
                    ret_t = self._llvm_type(self.current_lore.return_type)
                    if val.type != ret_t and isinstance(ret_t, ir.IntType):
                        val = self.builder.sext(val, ret_t)
                    self.builder.ret(val)
                else:
                    expr_type = self.sema.get_type(stmt.expr)
                    if expr_type in ("npc", "sigma"):
                        wide_val = self.builder.sext(val, self.i64_type) if val.type == self.i32_type else val
                        fmt_ptr = self.builder.bitcast(self.fmt_exit_int, self.i8p_type)
                        self.builder.call(self.printf_fn, [fmt_ptr, wide_val])
                    elif expr_type == "take":
                        t_p = self.builder.bitcast(self.str_true, self.i8p_type)
                        f_p = self.builder.bitcast(self.str_false, self.i8p_type)
                        sel_str = self.builder.select(val, t_p, f_p, name="bool_s")
                        fmt_ptr = self.builder.bitcast(self.fmt_exit_bool, self.i8p_type)
                        self.builder.call(self.printf_fn, [fmt_ptr, sel_str])
                    elif expr_type in self.struct_types:
                        prefix_g = self._get_cached_string("Program exit with result ")
                        self.builder.call(
                            self.printf_fn,
                            [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(prefix_g, self.i8p_type)],
                        )
                        slot = self._entry_alloca(val.type, name="exit_squad_slot")
                        self.builder.store(val, slot)
                        self._emit_print_squad_fields(slot, expr_type)
                        nl_g = self._get_cached_string("\n")
                        self.builder.call(
                            self.printf_fn,
                            [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(nl_g, self.i8p_type)],
                        )

                    self.builder.ret(ir.Constant(self.i32_type, 0))

    def _emit_squad_init(self, base_ptr: ir.Value, sq_name: str, init_node: SquadInitNode) -> None:
        sq_info = self.sema.squads[sq_name]
        for f_info, elem in zip(sq_info.fields, init_node.elements):
            f_ptr = self.builder.gep(
                base_ptr,
                [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, f_info.index)],
                inbounds=True,
                name=f"{f_info.name}_init_gep",
            )
            if isinstance(elem, SquadInitNode):
                self._emit_squad_init(f_ptr, f_info.type_name, elem)
            else:
                val = self._emit_expr(elem)
                self.builder.store(val, f_ptr)

    def _emit_expr(self, expr: ExprNode) -> ir.Value:
        match expr:
            case LiteralNode():
                t_name = self.sema.get_type(expr)
                if isinstance(expr.value, bool):
                    return ir.Constant(self.i1_type, 1 if expr.value else 0)
                if t_name == "sigma":
                    return ir.Constant(self.i64_type, expr.value)
                return ir.Constant(self.i32_type, expr.value)

            case VarNode():
                ptr = self._resolve_node_ptr(expr)
                return self.builder.load(ptr, name=expr.name)

            case ReadNode():
                slot = self._entry_alloca(self.i32_type, name="read_slot")
                fmt_ptr = self.builder.bitcast(self.fmt_d, self.i8p_type)
                self.builder.call(self.scanf_fn, [fmt_ptr, slot])
                return self.builder.load(slot, name="read_val")

            case BinOpNode():
                left_val = self._emit_expr(expr.left)
                right_val = self._emit_expr(expr.right)
                match expr.op:
                    case "+":
                        return self.builder.add(left_val, right_val)
                    case "-":
                        return self.builder.sub(left_val, right_val)
                    case "*":
                        return self.builder.mul(left_val, right_val)
                    case "==" | "🤝":
                        return self.builder.icmp_signed("==", left_val, right_val)
                    case "!=" | "💔":
                        return self.builder.icmp_signed("!=", left_val, right_val)
                    case _:
                        raise RuntimeError(f"Unknown operator '{expr.op}'")

            case CallNode():
                arg_vals = [self._emit_expr(a) for a in expr.args]
                call_kind, sq_name = self.sema.call_origins[id(expr)]
                if call_kind == "method" and sq_name is not None and self.current_this is not None:
                    callee_name = f"_squad_{sq_name}_{expr.func_name}"
                    callee = self.fn_map[callee_name]
                    return self.builder.call(callee, [self.current_this] + arg_vals)
                callee_name = f"_lore_{expr.func_name}"
                callee = self.fn_map[callee_name]
                return self.builder.call(callee, arg_vals)

            case FieldAccessNode():
                ptr = self._resolve_target_ptr_for_expr(expr.target)
                target_type = self.sema.get_type(expr.target)
                sq_info = self.sema.squads[target_type]
                f_info = sq_info.fields_by_name[expr.field_name]
                f_ptr = self.builder.gep(
                    ptr,
                    [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, f_info.index)],
                    inbounds=True,
                    name=f"{expr.field_name}_gep",
                )
                return self.builder.load(f_ptr, name=expr.field_name)

            case MemberCallNode():
                target_ptr = self._resolve_target_ptr_for_expr(expr.target)
                target_type = self.sema.get_type(expr.target)
                callee_name = f"_squad_{target_type}_{expr.method_name}"
                callee = self.fn_map[callee_name]
                arg_vals = [target_ptr] + [self._emit_expr(a) for a in expr.args]
                return self.builder.call(callee, arg_vals)

            case _:
                raise RuntimeError(f"Unhandled expr node '{type(expr).__name__}'")

    def _resolve_target_ptr_for_expr(self, expr: ExprNode) -> ir.Value:
        match expr:
            case VarNode():
                return self._resolve_node_ptr(expr)
            case FieldAccessNode():
                parent_ptr = self._resolve_target_ptr_for_expr(expr.target)
                parent_type = self.sema.get_type(expr.target)
                sq_info = self.sema.squads[parent_type]
                f_info = sq_info.fields_by_name[expr.field_name]
                return self.builder.gep(
                    parent_ptr,
                    [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, f_info.index)],
                    inbounds=True,
                    name=f"{expr.field_name}_gep",
                )
            case _:
                val = self._emit_expr(expr)
                slot = self._entry_alloca(val.type, name="temp_obj_slot")
                self.builder.store(val, slot)
                return slot

    def _emit_print(self, arg: ExprNode) -> None:
        if isinstance(arg, StringLiteralNode):
            g = self._get_cached_string(arg.value)
            str_ptr = self.builder.bitcast(g, self.i8p_type)
            fmt_s = self.builder.bitcast(self.fmt_s_nl, self.i8p_type)
            self.builder.call(self.printf_fn, [fmt_s, str_ptr])
            return

        arg_type = self.sema.get_type(arg)
        match arg_type:
            case "npc":
                val = self._emit_expr(arg)
                fmt = self.builder.bitcast(self.fmt_d_nl, self.i8p_type)
                self.builder.call(self.printf_fn, [fmt, val])
            case "sigma":
                val = self._emit_expr(arg)
                fmt = self.builder.bitcast(self.fmt_lld_nl, self.i8p_type)
                self.builder.call(self.printf_fn, [fmt, val])
            case "take":
                val = self._emit_expr(arg)
                t_p = self.builder.bitcast(self.str_true, self.i8p_type)
                f_p = self.builder.bitcast(self.str_false, self.i8p_type)
                sel_str = self.builder.select(val, t_p, f_p, name="bool_s")
                fmt = self.builder.bitcast(self.fmt_s_nl, self.i8p_type)
                self.builder.call(self.printf_fn, [fmt, sel_str])
            case _ if arg_type in self.struct_types:
                st_ptr = self._resolve_target_ptr_for_expr(arg)
                self._emit_print_squad_fields(st_ptr, arg_type)
                nl_g = self._get_cached_string("\n")
                self.builder.call(
                    self.printf_fn,
                    [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(nl_g, self.i8p_type)],
                )

    def _emit_print_squad_fields(self, st_ptr: ir.Value, sq_name: str) -> None:
        sq_info = self.sema.squads[sq_name]
        prefix_g = self._get_cached_string(f"{sq_name}{{")
        self.builder.call(
            self.printf_fn,
            [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(prefix_g, self.i8p_type)],
        )

        for idx, f in enumerate(sq_info.fields):
            if idx > 0:
                sep_g = self._get_cached_string(", ")
                self.builder.call(
                    self.printf_fn,
                    [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(sep_g, self.i8p_type)],
                )
            name_g = self._get_cached_string(f"{f.name}: ")
            self.builder.call(
                self.printf_fn,
                [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(name_g, self.i8p_type)],
            )

            f_ptr = self.builder.gep(
                st_ptr,
                [ir.Constant(self.i32_type, 0), ir.Constant(self.i32_type, idx)],
                inbounds=True,
                name=f"{f.name}_print_gep",
            )
            match f.type_name:
                case _ if f.type_name in self.struct_types:
                    self._emit_print_squad_fields(f_ptr, f.type_name)
                case "npc":
                    val = self.builder.load(f_ptr, name=f.name)
                    self.builder.call(self.printf_fn, [self.builder.bitcast(self.fmt_d, self.i8p_type), val])
                case "sigma":
                    val = self.builder.load(f_ptr, name=f.name)
                    self.builder.call(self.printf_fn, [self.builder.bitcast(self.fmt_lld, self.i8p_type), val])
                case "take":
                    val = self.builder.load(f_ptr, name=f.name)
                    t_p = self.builder.bitcast(self.str_true, self.i8p_type)
                    f_p = self.builder.bitcast(self.str_false, self.i8p_type)
                    sel_str = self.builder.select(val, t_p, f_p, name="bool_s")
                    self.builder.call(self.printf_fn, [self.builder.bitcast(self.fmt_s, self.i8p_type), sel_str])

        close_g = self._get_cached_string("}")
        self.builder.call(
            self.printf_fn,
            [self.builder.bitcast(self.fmt_s, self.i8p_type), self.builder.bitcast(close_g, self.i8p_type)],
        )


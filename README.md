# sigmalang

A custom programming language designed for the **Languages and Compilers Design** course (**Stage 1 & Stage 2**).  
Featuring brainrot/sigma-themed keywords (`lore`, `squad`, `canon`, `yap`, `is_this_real`), UTF-8 multi-byte emoji operators (`👈🏻`, `🤝`, `💔`), explicit mutability semantics, structures with member functions, and LLVM IR code generation via `llvmlite`.

---

## 1. Language Overview & Semantic Rules

The formal language grammar is defined in [`grammar.ebnf`](./grammar.ebnf).  
Below, every language construct is specified by **its semantic rule first**, followed by **its syntax and a short example**. Every rule is verified by positive (`tests/ok/`) and negative (`tests/err/`) test programs.

---

### 1.1 Types and Integer Overflow Rules

- **Rule (Primitive & Composite Types)**: Every variable, field, parameter, and expression has a static type: `npc` (32-bit signed integer, `i32`), `sigma` (64-bit signed integer, `i64`), `take` (boolean, `i1` with literals `hot` for `true` and `cringe` for `false`), or a user-defined structure type declared with `squad`. Implicit type conversions between `npc`, `sigma`, `take`, and `squad` types are forbidden; binary operators (`+`, `-`, `*`, `==`, `!=`, `🤝`, `💔`) require both operands to have the exact same type.
- **Rule (Integer Literal Overflow)**: Any integer literal must fit within the 64-bit signed integer range ($0 \dots 2^{63}-1$, max `9223372036854775807`). Furthermore, if an integer literal is used to initialize or assign to an `npc` (`i32`) target, it must not exceed the 32-bit signed maximum ($2^{31}-1 = 2147483647$).

```sigmalang
canon npc max_i32 👈🏻 2147483647
canon sigma big_val := 9223372036854775807
canonmaxing take is_based 👈🏻 hot
```

---

### 1.2 Variable Declarations, Scoping, and Mutability (`canon`, `yap`, `canonmaxing`)

- **Rule (Declaration Before Use & Single Declaration per Scope)**: Every variable must be declared before it is referenced. Re-declaring a variable with the same name in the same lexical scope is a compilation error.
- **Rule (Variable Mutability)**: Variables declared with `yap` are mutable and may be reassigned using `:=` or `👈🏻`. Variables declared with `canon` (compile-time constant) or `canonmaxing` (immutable binding) cannot be reassigned after initialization; any assignment to them is rejected by the semantic pass.

```sigmalang
canon npc LIMIT 👈🏻 100
yap npc score 👈🏻 10
score 👈🏻 score + 5
```

---

### 1.3 Control Flow (`is_this_real` / `nah` and Postfix `fr`)

- **Rule (Boolean Conditions & Non-Empty Blocks)**: The condition expression of an `is_this_real` block or a postfix `fr` modifier must have type `take` (`bool`). Both the `is_this_real` branch and the optional `nah` branch must contain at least one statement.

```sigmalang
is_this_real score 🤝 15 {
    score 👈🏻 score * 2
} nah {
    score 👈🏻 0
}

exit score fr score == 30
```

---

### 1.4 Functions (`lore`)

- **Rule (Function Signatures, Arguments & Return Types)**: A function is declared with `lore name(type1 param1, ...) -> return_type { ... }`. A function call is an expression whose argument count and argument types must exactly match the declared parameter list. Every execution path that leaves a function via `exit <factor>` must return a value whose type matches the function's declared `return_type`.
- **Rule (What a Function Body Can See)**: Inside a `lore` function body, a name lookup resolves in the following order:
  1. Local variables declared earlier in the current (or enclosing) block of the function and the function's parameters (parameters are immutable bindings).
  2. Top-level global variables declared before the function.
  3. Any `lore` function declared anywhere in the program — a function may call itself recursively and may call any function declared **below** it in the source file.

```sigmalang
lore add(npc a, npc b) -> npc {
    canon npc res 👈🏻 a + b
    exit res
}

lore compute(npc x) -> npc {
    exit add(add(x, 1), double_val(x))
}

lore double_val(npc v) -> npc {
    exit (v * 2)
}
```

---

### 1.5 Structures with Fields (`squad`)

- **Rule (Structure Declaration & Object Initialization)**: A structure is declared with `squad Name { ... }` and must contain at least one field before any member functions. Each field has an explicit mutability marker (`canon`, `canonmaxing`, or `yap`), a type, and a unique name within the structure. An object of type `Name` is initialized with `{ v1, v2, ... }`, providing exactly one value of the matching type for every field in declaration order.
- **Rule (Field Access & Chain Mutability)**: A field is accessed by name with `.` (`p.x`) and can be chained across nested structures (`c.center.x`). Reading a field is allowed on any object (`canon`, `canonmaxing`, or `yap`). **Assigning to a field (`a.b.c 👈🏻 val`) is allowed if and only if the base variable `a` AND every intermediate and final field in the chain (`b`, `c`) is declared mutable with `yap`**. If any step in the chain is `canon` or `canonmaxing`, the semantic pass reports an error.

```sigmalang
squad Point {
    yap npc x
    yap npc y
}

squad Circle {
    yap Point center
    canon npc radius
}

yap Circle c 👈🏻 { { 3, 4 }, 10 }
c.center.x 👈🏻 7
```

---

### 1.6 Member Functions (`lore` inside `squad`)

- **Rule (Name Lookup Order Inside a Member Function)**: Inside a member function of a `squad`, when a parameter/local variable, a structure field (or member function), and a global share the same name, the name is looked up strictly in this order:
  1. **Parameters and local variables** of the member function (shadowing both fields and globals);
  2. **Fields and other member functions** of the enclosing `squad` (visible directly by name without a prefix);
  3. **Top-level globals** (global variables and top-level `lore` functions).
- **Rule (Mutating Member Functions on Constant vs. Mutable Objects)**: A member function is classified as **mutating** if it directly assigns to any field of its `squad` or calls another mutating member function on the current object (or its fields). **A mutating member function may only be called on an object reached through a chain that is mutable (`yap`) at every step**. Calling a mutating member function on a `canon` or `canonmaxing` object (or through a non-`yap` field) is a semantic error. Non-mutating member functions may be called on any object.

```sigmalang
squad Point {
    yap npc x
    yap npc y

    lore d2() -> npc {
        canon npc r 👈🏻 x * x + y * y
        exit r
    }

    lore shift(npc dx) -> npc {
        x 👈🏻 x + dx
        exit x
    }
}

canon Point fixed_pt 👈🏻 { 3, 4 }
canon npc dist 👈🏻 fixed_pt.d2()

yap Point moving_pt 👈🏻 { 3, 4 }
canon npc moved_x 👈🏻 moving_pt.shift(5)
```

---

### 1.7 Built-in Input and Output (`read` and `print`)

- **Rule (`read` Built-in Expression)**: `read()` is a built-in expression that takes zero arguments, reads one signed 32-bit integer from standard input (`stdin`), and evaluates to a value of type `npc` (`i32`).
- **Rule (`print` Built-in Statement, Object Formatting & Newline Placement)**: `print(...)` is a statement (not an expression; it produces no value) that accepts a single argument of type `npc`, `sigma`, `take`, a string literal `"..."`, or a `squad` object. **`print` always outputs a single newline character (`\n`) at the very end of the printed item**:
  - `npc` (`i32`) is printed as a signed decimal integer (`%d\n`).
  - `sigma` (`i64`) is printed as a signed 64-bit decimal integer (`%lld\n`).
  - `take` (`bool`) is printed as the word `true` (when `hot`) or `false` (when `cringe`), followed by `\n`.
  - A string literal `"text"` (allowed only as the argument of `print`) prints its characters followed by `\n`.
  - A `squad` object is printed as its type name and fields in declaration order in the format `SquadName{field1: val1, field2: val2}` (recursively formatting nested structures and booleans as `true`/`false` without intermediate newlines), followed by a single trailing `\n`.

```sigmalang
yap Point p 👈🏻 { read(), read() }
print("Point read from input:")
print(p)
print(p.d2())
print(hot)
```
For input `3 4`, the program above prints:
```text
Point read from input:
Point{x: 3, y: 4}
25
true
```

---

## 2. Requirements & Setup

### Environment
- Python 3.12+
- `llvmlite` (for LLVM IR generation via `llvmlite.ir`)
- LLVM / Clang toolchain (`clang`, `llc`, or `lli`) for compiling and running generated `.ll` modules.

```bash
# Activate the course environment (or local .venv with llvmlite installed)
source ~/lcd/bin/activate
```

---

## 3. How to Build and Run

### 3.1 Compile to LLVM IR and Run
```bash
# 1. Generate LLVM IR module to output.ll
python3 compiler.py examples/simple_example.txt output.ll

# 2. Link with clang and execute
clang -x ir output.ll -o program -Wno-override-module
./program
```

Or in a single step via `./run.sh`:
```bash
./run.sh examples/simple_example.txt
```

### 3.2 Print the AST (`--ast`)
```bash
python3 compiler.py --ast tests/ok/var_decl_canon.src
```

### 3.3 Error Reporting
On any lexical, syntax, or semantic error, the compiler prints a single diagnostic line to `stderr`, exits with a non-zero status code, and produces no `.ll` output file:
```text
compilation error: line 1:16: integer literal overflow: '2147483648' exceeds 32-bit integer range for type 'npc'
```

---

## 4. Running the Test Suite

Run all automated tests (AST tests, end-to-end LLVM IR execution tests with `.expected` and `.in`, and negative error tests with `.err`):
```bash
./run_tests.sh
```

---

## 5. VS Code Extension

A companion Visual Studio Code extension providing syntax highlighting and emoji snippets for `sigmaLang` is located in [`./vscode-sigmalang-support`](./vscode-sigmalang-support):
- Pre-packaged VSIX package: [`vscode-sigmalang-support/sigmalang-support-0.1.0.vsix`](./vscode-sigmalang-support/sigmalang-support-0.1.0.vsix).

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

### 1.7 Built-in Input and Output (`absorb` and `spit_fax`)

- **Rule (`absorb` Built-in Expression)**: `absorb()` is a built-in expression that takes zero arguments, reads one signed 32-bit integer from standard input (`stdin`), and evaluates to a value of type `npc` (`i32`).
- **Rule (`spit_fax` Built-in Statement, Object Formatting & Newline Placement)**: `spit_fax(...)` is a statement (not an expression; it produces no value) that accepts a single argument of type `npc`, `sigma`, `take`, a string literal `"..."`, or a `squad` object. **`spit_fax` always outputs a single newline character (`\n`) at the very end of the printed item**:
  - `npc` (`i32`) is printed as a signed decimal integer (`%d\n`).
  - `sigma` (`i64`) is printed as a signed 64-bit decimal integer (`%lld\n`).
  - `take` (`bool`) is printed as the word `true` (when `hot`) or `false` (when `cringe`), followed by `\n`.
  - A string literal `"text"` (allowed only as the argument of `spit_fax`) prints its characters followed by `\n`.
  - A `squad` object is printed as its type name and fields in declaration order in the format `SquadName{field1: val1, field2: val2}` (recursively formatting nested structures and booleans as `true`/`false` without intermediate newlines), followed by a single trailing `\n`.

```sigmalang
yap Point p 👈🏻 { absorb(), absorb() }
spit_fax("Point read from input:")
spit_fax(p)
spit_fax(p.d2())
spit_fax(hot)
```
For input `3 4`, the program above prints:
```text
Point read from input:
Point{x: 3, y: 4}
25
true
```

---

### 1.8 Loops & Control Flow (`as_long_as` / `while`, `streak` / `for`, `ragequit` / `break`) [Stage 3 Feature]

- **Rule (`as_long_as` / `while`)**: An `as_long_as` (or `while`) loop checks a condition expression before every iteration. The condition must be of boolean type `take` (`bool`). If the condition evaluates to `hot` (`true`), the loop body executes; otherwise, control transfers to the loop exit block.
- **Rule (`streak` / `for` over integer range)**: A `streak` (or `for`) loop iterates an induction variable over a half-open integer range `start .. end` (`[start, end)`). Both `start` and `end` bounds must be integer expressions of the same type (`npc` or `sigma`). The loop induction variable is implicitly declared with `canon` in the loop's local scope and increments by 1 at the end of each iteration until reaching or exceeding `end`.
- **Rule (Local Scoping & Nesting)**: Each loop iteration executes within its own local scope. Variables declared in the loop body shadow outer declarations and cannot be accessed outside the loop. Loops may be nested arbitrarily inside other loops, functions, or conditionals.
- **Rule (`ragequit` / `break`)**: An optional `ragequit` (or `break`) statement immediately terminates the innermost enclosing loop and transfers control to its exit block. Using `ragequit` outside of a loop is a compile-time semantic error. `ragequit` also supports conditional execution via postfix `fr` (e.g. `ragequit fr i == 5;`).

#### Example 1: `as_long_as` loop with postfix `ragequit`
```sigmalang
yap npc sum := 0;
yap npc i := 0;
as_long_as hot {
    sum := sum + i;
    i := i + 1;
    ragequit fr i == 5;
}
spit_fax(sum); # prints 10
```

#### Example 2: Nested `streak` loop with range iteration
```sigmalang
yap npc total := 0;
streak r in 0 .. 3 {
    streak c in 0 .. 4 {
        total := total + 1;
    }
}
spit_fax(total); # prints 12
```
for r in 0 .. 3 {
    for c in 0 .. 4 {
        total := total + 1;
    }
}
spit_fax(total); # prints 12
```

#### LLVM IR Excerpt & Explanation (Task 1 Deliverable)
Below is an excerpt of the LLVM IR produced by `LLVMCodeGenerator` for a `while` loop:

```llvm
while.cond:
  %"i" = load i32, i32* @"_global_i"
  %".4" = icmp slt i32 %"i", 5
  br i1 %".4", label %"while.body", label %"while.exit"
while.body:
  %"sum" = load i32, i32* @"_global_sum"
  %"i.1" = load i32, i32* @"_global_i"
  %".6" = add i32 %"sum", %"i.1"
  store i32 %".6", i32* @"_global_sum"
  %"i.2" = load i32, i32* @"_global_i"
  %".8" = add i32 %"i.2", 1
  store i32 %".8", i32* @"_global_i"
  br label %"while.cond"
while.exit:
```

* **Condition block (`while.cond`)**: Loads the loop variable, compares it against the bound with `icmp slt`, and performs conditional branching (`br i1 ...`) to either enter `while.body` or leave through `while.exit`.
* **Body block & back edge (`while.body`)**: Executes the loop statements in a nested variable scope and finishes with an unconditional branch `br label %"while.cond"` — the **back edge** that routes execution back to the condition check for the next iteration.
* **Exit block (`while.exit`)**: Acts as the merge target reached either when the loop condition evaluates to false (`cringe`) or when a `break` statement transfers control directly out of the loop.

---

### 1.9 The Optimizer (`--optimize`) [Stage 3 Task 2]

The optimizer operates on the checked AST before LLVM IR generation whenever `--optimize` is provided anywhere on the command line:

1. **Unused variables**: Declarations and assignments that are never read are iteratively removed until fixpoint. Scopes and shadowing are respected. Crucially, expressions calling functions or performing input (`absorb()`) are preserved for their side effects.
2. **Unused functions**: Functions that are never called across the program are removed with their entire bodies to a fixpoint (removing one body may leave another function unused).
3. **Inlining**: Functions called exactly once are replaced at their call site by their body:
   - Parameters become local declarations initialized with the argument expressions.
   - Names are alpha-renamed (e.g. `_inl_1_param`) to guarantee no name collisions with the caller's scope.
   - The expression of the trailing `exit` statement stands in place of the call.
   - The inlined function definition is subsequently removed as unused.
   - **Inlining Shapes & Restrictions**: Recursive functions (direct or indirect cycle in the call graph) are **never** inlined. Functions with multiple exit points (e.g. exiting inside an `is_this_real` branch) are left alone; inlining only targets functions ending in a single terminal `exit`.

#### LLVM IR Before & After Excerpt (Function Inlining)

**Source:**
```sigmalang
lore double_val(npc x) -> npc {
    exit (x * 2);
}
yap npc num := 21;
yap npc result := double_val(num);
spit_fax(result);
```

**Before `--optimize` (with function call):**
```llvm
define i32 @"_lore_double_val"(i32 %"x") {
entry:
  %"x_slot" = alloca i32
  store i32 %"x", i32* %"x_slot"
  %"x.1" = load i32, i32* %"x_slot"
  %".4" = mul i32 %"x.1", 2
  ret i32 %".4"
}
define i32 @"main"() {
entry:
  store i32 21, i32* @"_global_num"
  %"num" = load i32, i32* @"_global_num"
  %".3" = call i32 @"_lore_double_val"(i32 %"num")
  store i32 %".3", i32* @"_global_result"
  ...
```

**After `--optimize` (inlined & pruned):**
```llvm
define i32 @"main"() {
entry:
  store i32 21, i32* @"_global_num"
  %"num" = load i32, i32* @"_global_num"
  store i32 %"num", i32* @"_global__inl_1_x"
  %"_inl_1_x" = load i32, i32* @"_global__inl_1_x"
  %".4" = mul i32 %"_inl_1_x", 2
  store i32 %".4", i32* @"_global_result"
  ...
```
* Notice that `_lore_double_val` has been completely eliminated from the LLVM module, and the call site `%".3" = call i32 @"_lore_double_val"(...)` in `main` was replaced by the inlined parameter storage and direct arithmetic computation.

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
# 1. Generate LLVM IR module to output.ll (unoptimized or optimized)
python3 compiler.py examples/simple_example.txt output.ll
python3 compiler.py examples/simple_example.txt output.ll --optimize

# 2. Run via lli or compile with clang
lli output.ll
```

Or compile and run in a single step via `./run.sh` (automatically feeds `NAME.in` to `stdin` if present):
```bash
./run.sh examples/simple_example.txt
./run.sh examples/simple_example.txt --optimize
./run.sh examples/04_read_and_print.src
```

### 3.2 Print the AST (`--ast`)
```bash
# Dump initial AST
python3 compiler.py --ast examples/simple_example.txt

# Dump optimized AST after running the optimizer
python3 compiler.py --ast --optimize examples/simple_example.txt
# or via run.sh:
./run.sh --ast --optimize examples/simple_example.txt
```

### 3.3 Error Reporting
On any lexical, syntax, or semantic error, the compiler prints a single diagnostic line to `stderr` with exact `line:col` coordinates, exits with a non-zero status code, and produces no `.ll` output file:
```text
compilation error: line 11:16: cannot call mutating member function 'shift' on canon variable 'p'
```

### 3.4 The Real Program: Sigma Blackjack (`programs/sigma_blackjack.txt`)

`sigma_blackjack.txt` is an interactive console Blackjack (21) game built entirely in `sigmaLang`.
The player starts with 100 chips, enters a lucky seed to initialize the deterministic LCG pseudo-random number generator, and plays consecutive rounds against the dealer.
The game encapsulates table state inside a `squad BlackjackTable` structure with 6 mutating member functions (`reset_round`, `deal_player`, `deal_dealer`, `deal_dealer_hidden`, `reveal_dealer_hidden`, `payout`).
Global `lore` functions (`next_seed`, `get_card_val`) implement bounded arithmetic pseudo-random card generation without relying on external libraries.
The program prominently uses the Stage 3 Loop feature in multiple critical mechanics:
1. `as_long_as table.chips > 0` drives the interactive outer game loop, with `ragequit` providing voluntary cash-out when the player enters `0`.
2. `as_long_as player_turn == 1` manages player decision-making (Hit `1`, Stand `2`, or Double Down `3`), while `as_long_as table.dealer_score < 17` enforces dealer drawing rules.
3. `streak p_i in 1 .. 3` executes initial two-card player dealing.
4. `as_long_as rem >= 2` computes the 3:2 blackjack payout multiplier using repeated subtraction loops.

#### Compiling to a Native Executable (`llc` + `clang`)
```bash
# 1. Compile sigmaLang source into LLVM IR:
python3 compiler.py programs/sigma_blackjack.txt programs/sigma_blackjack.ll

# 2. Compile LLVM IR into a native object file:
llc -filetype=obj -relocation-model=pic programs/sigma_blackjack.ll -o programs/sigma_blackjack.o

# 3. Link into a standalone native binary with clang:
clang -fPIE programs/sigma_blackjack.o -o programs/sigma_blackjack

# 4. Run interactively or pipe inputs:
./programs/sigma_blackjack
```

#### Running Recorded Sessions
```bash
# Session 1 (Double Down & Win):
./programs/sigma_blackjack < programs/sigma_blackjack_session1.in

# Session 2 (Multiple Hits & Bust):
./programs/sigma_blackjack < programs/sigma_blackjack_session2.in
```

---

## 4. Running the Test Suite

Run all 77 automated tests (Stage 1 AST & error tests, Stage 2 end-to-end LLVM IR execution tests with `.expected` and `.in`, Stage 2 negative semantic error tests with `.err`, Stage 3 loop tests, Stage 3 optimizer transformation tests with equivalence checks, and Stage 3 native binary real program sessions):
```bash
./run_tests.sh
```

---

## 5. VS Code Extension (Extra Feature)

A companion Visual Studio Code extension providing syntax highlighting and code snippets for **Stage 1 & Stage 2** of `sigmaLang` is located in [`./vscode-sigmalang-support`](./vscode-sigmalang-support):
- **Syntax Highlighting** ([`syntaxes/sigmalang.tmLanguage.json`](./vscode-sigmalang-support/syntaxes/sigmalang.tmLanguage.json)): highlights `squad` and `lore` declarations, built-in I/O (`absorb`, `spit_fax`), mutability modifiers (`canon`, `yap`, `canonmaxing`), control flow (`is_this_real`, `nah`, `fr`, `exit`), primitive and user-defined `squad` types, string literals (`"..."`), function calls, and emoji/arrow operators (`👈🏻`, `🤝`, `💔`, `->`).
- **Code & Emoji Snippets** ([`snippets/snippets.json`](./vscode-sigmalang-support/snippets/snippets.json)): auto-completion templates for `lore` functions, `squad` structures, `spit_fax(...)`, `absorb()`, variable declarations, and emoji operators.
- **Pre-packaged VSIX package**: [`vscode-sigmalang-support/sigmalang-support-0.1.0.vsix`](./vscode-sigmalang-support/sigmalang-support-0.1.0.vsix).

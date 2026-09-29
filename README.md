# sigmaLang

A custom programming language designed for **Stage 1** of the Languages and Compilers Design course. 
Featuring brainrot/sigma-themed keywords, UTF-8 multi-byte emoji operators, and explicit immutability semantics.

---

## 1. Language Overview & Features

The formal language grammar is defined in [`grammar.ebnf`](./grammar.ebnf).

### 1.1 Types
`sigmaLang` supports three primitive types:
- `npc` — 32-bit signed integer (range $0 \dots 2^{31}-1$).
- `sigma` — 64-bit signed integer (range $0 \dots 2^{63}-1$).
- `take` — Boolean type with literals `hot` (`true`) and `cringe` (`false`).

### 1.2 Immutability & Variable Kinds
Declarations require explicit mutability markers:
- `canon` — Immutable compile-time constant.
- `yap` — Mutable variable that can be reassigned.
- `canonmaxing` — Immutable variable (cannot be reassigned after declaration).

### 1.3 Operators
- **Assignment**: `:=` or multi-byte UTF-8 emoji `👈🏻` (U+1F448 + U+1F3FB).
- **Comparison**: `==`, `!=`, or emojis `🤝` (equality) and `💔` (inequality). Produces a `take` (`bool`).
- **Arithmetic**: `+`, `-` (lower precedence), `*` (higher precedence).
- **Grouping**: Parentheses `( expr )`.
- **Comments**: Start with `#` and extend to the end of the line.

### 1.4 Control Flow (`if / else`)
Conditional blocks require at least one statement in each branch:
```sigmalang
is_this_real hot {
    yap npc count 👈🏻 1
    count 👈🏻 count + 1
} nah {
    exit cringe
}
```

### 1.5 Syntax Examples

| Feature | Code Example |
|---|---|
| Constant declaration | `canon npc MAX_VAL 👈🏻 100` |
| Mutable variable | `yap sigma score := 250` |
| Assignment | `score 👈🏻 score * 2` |
| Boolean take | `canonmaxing take is_based 👈🏻 hot` |
| Arithmetic & Parentheses | `canon npc res 👈🏻 (10 + 5) * 2` |
| Comparison | `canon take valid 👈🏻 score 🤝 500` |
| Conditional block | `is_this_real valid { exit score }` |
| Exit statement | `exit 0` |

---

## 2. Requirements & Setup

### Environment
- Python 3.12+
- No external libraries required (pure standard library).

```bash
# Optional: create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. How to Run the Compiler

The compiler entry point is `compiler.py`. It accepts source files and produces an Abstract Syntax Tree (AST) dump via `--ast`:

```bash
# Using python directly:
python3 compiler.py --ast tests/ok/var_decl_canon.src

# Using the helper runner script:
./run.sh tests/ok/var_decl_canon.src
```

### Error Reporting
On lexical or syntax errors, the compiler outputs a single line to `stderr` and exits with a non-zero exit code:
```
compilation error: line 1:16: integer literal overflow: '2147483648' exceeds 32-bit integer range for type 'npc'
```

---

## 4. How to Run the Tests

The test suite contains **34 automated tests** (18 happy path and 16 error scenarios covering edge cases and boundary conditions):
- `tests/ok/`: Valid programs verified against expected `.ast` outputs.
- `tests/err/`: Invalid programs verified against expected `.err` compiler diagnostic messages.

Run all tests with:
```bash
./run_tests.sh
```

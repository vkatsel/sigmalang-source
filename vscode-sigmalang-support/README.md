# sigmalang Language Support for VS Code

Official Visual Studio Code extension for the **sigmalang** programming language (**Stage 1 & Stage 2**).

## Features
- **Syntax Highlighting**: Full color highlighting for `sigmalang` declarations (`squad`, `lore`, `canon`, `yap`, `canonmaxing`), control flow (`is_this_real`, `nah`, `fr`, `exit`), built-in I/O (`absorb`, `spit_fax`), types (`npc`, `sigma`, `take`, and capitalized `squad` names), string literals (`"..."`), boolean constants (`hot`, `cringe`), operators (`👈🏻`, `🤝`, `💔`, `->`), and comments (`#`).
- **Emoji Snippets & Auto-completion**: Fast typing of emojis and Stage 1/Stage 2 constructs:
  - `assign` / `hand` / `<-` $\rightarrow$ `👈🏻`
  - `eq` / `shake` $\rightarrow$ `🤝`
  - `neq` / `broken` $\rightarrow$ `💔`
  - `lore` / `fn` $\rightarrow$ `lore name(...) -> type { ... }` function template.
  - `squad` / `struct` $\rightarrow$ `squad Name { ... }` structure template.
  - `spit_fax` / `print` $\rightarrow$ `spit_fax(...)` output statement.
  - `absorb` / `read` $\rightarrow$ `absorb()` input expression.
  - `canon`, `yap`, `canonmaxing` $\rightarrow$ variable declaration snippets.
  - `if`, `ifelse` $\rightarrow$ `is_this_real` / `nah` control blocks.

## How to Install

### Option 1: Install from VSIX package (One click)
1. Open Visual Studio Code.
2. Go to the Extensions view (`Ctrl+Shift+X`).
3. Click the `...` (Views and More Actions) menu in the top right corner.
4. Select **Install from VSIX...**.
5. Select the `sigmalang-support-0.1.0.vsix` file located in this directory.

### Option 2: Copy to extensions folder
Copy the `vscode-sigmalang-support` folder directly into your VS Code extensions directory:
- Linux / macOS: `~/.vscode/extensions/sigmalang-support`
- Windows: `%USERPROFILE%\.vscode\extensions\sigmalang-support`

# sigmalang Language Support for VS Code

Official Visual Studio Code extension for the **sigmalang** programming language.

## Features
- **Syntax Highlighting**: Full color highlighting for `sigmalang` keywords, types (`npc`, `sigma`, `take`), constants, operators, and comments.
- **Emoji Snippets & Auto-completion**: Fast typing of emojis and code constructs:
  - `assign` / `hand` / `<-` $\rightarrow$ `👈🏻`
  - `eq` / `shake` $\rightarrow$ `🤝`
  - `neq` / `broken` $\rightarrow$ `💔`
  - `canon`, `yap`, `canonmaxing` $\rightarrow$ variable declaration snippets.
  - `if`, `ifelse` $\rightarrow$ `is_this_real` control blocks.

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

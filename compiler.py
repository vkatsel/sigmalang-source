import sys
from pathlib import Path

from src.lexer import Lexer, LexerError
from src.parser import Parser, ParserError

def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: python3 compiler.py --ast <source_file>\n")
        sys.exit(1)

    ast_mode = False
    file_path: Path | None = None

    for arg in args:
        if arg == "--ast":
            ast_mode = True
        elif file_path is None:
            file_path = Path(arg)
        else:
            sys.stderr.write(f"compilation error: unexpected argument '{arg}'\n")
            sys.exit(1)

    if file_path is None:
        sys.stderr.write("compilation error: no input file provided\n")
        sys.exit(1)

    if not file_path.exists():
        sys.stderr.write(f"compilation error: file '{file_path}' not found\n")
        sys.exit(1)

    try:
        source_bytes = file_path.read_bytes()
        lexer = Lexer(source_bytes)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        if ast_mode:
            print(ast.dump())
    except (LexerError, ParserError) as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"compilation error: internal error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

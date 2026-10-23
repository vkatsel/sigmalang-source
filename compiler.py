import sys
from pathlib import Path

# Ensure llvmlite from ~/lcd is accessible
for _p in (
    "/home/ubuntu/lcd/lib/python3.12/site-packages",
    str(Path.home() / "lcd/lib/python3.12/site-packages"),
):
    if _p not in sys.path and Path(_p).exists():
        sys.path.insert(0, _p)

from src.lexer import Lexer, LexerError
from src.parser import Parser, ParserError
from src.sema import SemanticAnalyzer, SemanticError
from src.codegen import LLVMCodeGenerator

def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: python3 compiler.py <source_file> <output.ll>\n"
                         "   OR: python3 compiler.py --ast <source_file>\n")
        sys.exit(1)

    if args[0] == "--ast":
        if len(args) != 2:
            sys.stderr.write("compilation error: --ast requires exactly one source file\n")
            sys.exit(1)
        file_path = Path(args[1])
        if not file_path.exists():
            sys.stderr.write(f"compilation error: file '{file_path}' not found\n")
            sys.exit(1)

        try:
            source_bytes = file_path.read_bytes()
            lexer = Lexer(source_bytes)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()
            print(ast.dump())
            sys.exit(0)
        except (LexerError, ParserError) as e:
            sys.stderr.write(f"{e}\n")
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"compilation error: internal error: {e}\n")
            sys.exit(1)

    if len(args) != 2:
        sys.stderr.write("Usage: python3 compiler.py <source_file> <output.ll>\n")
        sys.exit(1)

    input_path = Path(args[0])
    output_path = Path(args[1])

    if not input_path.exists():
        sys.stderr.write(f"compilation error: file '{input_path}' not found\n")
        sys.exit(1)

    try:
        source_bytes = input_path.read_bytes()
        lexer = Lexer(source_bytes)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        sema = SemanticAnalyzer()
        sema.analyze(ast)

        codegen = LLVMCodeGenerator(sema)
        module = codegen.generate(ast)

        output_path.write_text(str(module), encoding="utf-8")
        sys.exit(0)
    except (LexerError, ParserError, SemanticError) as e:
        sys.stderr.write(f"{e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"compilation error: internal error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

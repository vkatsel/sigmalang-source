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
from src.optimizer import ASTOptimizer

def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: python3 compiler.py <source_file> <output.ll> [--optimize]\n"
                         "   OR: python3 compiler.py --ast <source_file> [--optimize]\n")
        sys.exit(1)

    optimize = "--optimize" in args
    clean_args = [a for a in args if a != "--optimize"]

    if "--ast" in clean_args:
        ast_args = [a for a in clean_args if a != "--ast"]
        if len(ast_args) != 1:
            sys.stderr.write("compilation error: --ast requires exactly one source file\n")
            sys.exit(1)
        file_path = Path(ast_args[0])
        if not file_path.exists():
            sys.stderr.write(f"compilation error: file '{file_path}' not found\n")
            sys.exit(1)

        try:
            source_bytes = file_path.read_bytes()
            lexer = Lexer(source_bytes)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            ast = parser.parse()

            if optimize:
                sema = SemanticAnalyzer()
                sema.analyze(ast)
                optimizer = ASTOptimizer()
                ast = optimizer.optimize(ast, sema)

            print(ast.dump())
            sys.exit(0)
        except (LexerError, ParserError, SemanticError) as e:
            sys.stderr.write(f"{e}\n")
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"compilation error: internal error: {e}\n")
            sys.exit(1)

    if len(clean_args) != 2:
        sys.stderr.write("Usage: python3 compiler.py <source_file> <output.ll> [--optimize]\n")
        sys.exit(1)

    input_path = Path(clean_args[0])
    output_path = Path(clean_args[1])

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

        if optimize:
            optimizer = ASTOptimizer()
            ast = optimizer.optimize(ast, sema)

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

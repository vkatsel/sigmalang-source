import enum
from dataclasses import dataclass

class LexerError(Exception):
    def __init__(self, line: int, col: int, message: str) -> None:
        self.line = line
        self.col = col
        self.message = message
        super().__init__(f"compilation error: line {line}:{col}: {message}")

class TokenKind(enum.StrEnum):
    # Keywords - Var Kinds
    CANON = "canon"
    YAP = "yap"
    CANONMAXING = "canonmaxing"

    # Keywords - Types
    TYPE_NPC = "npc"
    TYPE_SIGMA = "sigma"
    TYPE_TAKE = "take"

    # Keywords - Control & Builtins
    IS_THIS_REAL = "is_this_real"
    NAH = "nah"
    EXIT = "exit"

    # Boolean Literals
    HOT = "hot"
    CRINGE = "cringe"

    # Identifiers & Number Literals
    IDENT = "IDENT"
    NUMBER = "NUMBER"

    # Operators & Delimiters
    ASSIGN = ":="
    EMOJI_ASSIGN = "👈🏻"
    EQ = "=="
    NEQ = "!="
    EMOJI_EQ = "🤝"
    EMOJI_NEQ = "💔"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    SEMICOLON = ";"

    EOF = "EOF"

KEYWORDS: dict[str, TokenKind] = {
    "canon": TokenKind.CANON,
    "yap": TokenKind.YAP,
    "canonmaxing": TokenKind.CANONMAXING,
    "npc": TokenKind.TYPE_NPC,
    "sigma": TokenKind.TYPE_SIGMA,
    "take": TokenKind.TYPE_TAKE,
    "is_this_real": TokenKind.IS_THIS_REAL,
    "nah": TokenKind.NAH,
    "exit": TokenKind.EXIT,
    "hot": TokenKind.HOT,
    "cringe": TokenKind.CRINGE,
}

EMOJI_ASSIGN_BYTES = "👈🏻".encode("utf-8")
EMOJI_EQ_BYTES = "🤝".encode("utf-8")
EMOJI_NEQ_BYTES = "💔".encode("utf-8")

@dataclass(slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    col: int

class Lexer:
    def __init__(self, source_bytes: bytes) -> None:
        self.bytes = source_bytes
        self.pos = 0
        self.length = len(source_bytes)
        self.line = 1
        self.col = 1

    def _peek_byte(self, offset: int = 0) -> int | None:
        idx = self.pos + offset
        if idx < self.length:
            return self.bytes[idx]
        return None

    def _advance_byte(self) -> int:
        b = self.bytes[self.pos]
        self.pos += 1
        if b == ord("\n"):
            self.line += 1
            self.col = 1
        elif (b & 0xC0) != 0x80:
            self.col += 1
        return b

    def _matches_sequence(self, seq: bytes) -> bool:
        if self.pos + len(seq) > self.length:
            return False
        return self.bytes[self.pos : self.pos + len(seq)] == seq

    def _consume_sequence(self, seq: bytes) -> None:
        for _ in range(len(seq)):
            self._advance_byte()

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []

        while self.pos < self.length:
            b = self.bytes[self.pos]

            if b in (ord(" "), ord("\t"), ord("\r"), ord("\n")):
                self._advance_byte()
                continue

            if b == ord("#"):
                while self.pos < self.length and self.bytes[self.pos] != ord("\n"):
                    self._advance_byte()
                continue

            tok_line = self.line
            tok_col = self.col

            if self._matches_sequence(EMOJI_ASSIGN_BYTES):
                self._consume_sequence(EMOJI_ASSIGN_BYTES)
                tokens.append(Token(TokenKind.EMOJI_ASSIGN, "👈🏻", tok_line, tok_col))
                continue

            if self._matches_sequence(EMOJI_EQ_BYTES):
                self._consume_sequence(EMOJI_EQ_BYTES)
                tokens.append(Token(TokenKind.EMOJI_EQ, "🤝", tok_line, tok_col))
                continue

            if self._matches_sequence(EMOJI_NEQ_BYTES):
                self._consume_sequence(EMOJI_NEQ_BYTES)
                tokens.append(Token(TokenKind.EMOJI_NEQ, "💔", tok_line, tok_col))
                continue

            if b == ord(":"):
                self._advance_byte()
                if self._peek_byte() == ord("="):
                    self._advance_byte()
                    tokens.append(Token(TokenKind.ASSIGN, ":=", tok_line, tok_col))
                    continue
                raise LexerError(tok_line, tok_col, "unexpected character ':', expected ':='")

            if b == ord("="):
                self._advance_byte()
                if self._peek_byte() == ord("="):
                    self._advance_byte()
                    tokens.append(Token(TokenKind.EQ, "==", tok_line, tok_col))
                    continue
                raise LexerError(tok_line, tok_col, "unexpected character '=', expected '=='")

            if b == ord("!"):
                self._advance_byte()
                if self._peek_byte() == ord("="):
                    self._advance_byte()
                    tokens.append(Token(TokenKind.NEQ, "!=", tok_line, tok_col))
                    continue
                raise LexerError(tok_line, tok_col, "unexpected character '!', expected '!='")

            if b == ord("+"):
                self._advance_byte()
                tokens.append(Token(TokenKind.PLUS, "+", tok_line, tok_col))
                continue

            if b == ord("-"):
                self._advance_byte()
                tokens.append(Token(TokenKind.MINUS, "-", tok_line, tok_col))
                continue

            if b == ord("*"):
                self._advance_byte()
                tokens.append(Token(TokenKind.STAR, "*", tok_line, tok_col))
                continue

            if b == ord("("):
                self._advance_byte()
                tokens.append(Token(TokenKind.LPAREN, "(", tok_line, tok_col))
                continue

            if b == ord(")"):
                self._advance_byte()
                tokens.append(Token(TokenKind.RPAREN, ")", tok_line, tok_col))
                continue

            if b == ord("{"):
                self._advance_byte()
                tokens.append(Token(TokenKind.LBRACE, "{", tok_line, tok_col))
                continue

            if b == ord("}"):
                self._advance_byte()
                tokens.append(Token(TokenKind.RBRACE, "}", tok_line, tok_col))
                continue

            if b == ord(";"):
                self._advance_byte()
                tokens.append(Token(TokenKind.SEMICOLON, ";", tok_line, tok_col))
                continue

            if ord("0") <= b <= ord("9"):
                num_bytes = bytearray()
                while self.pos < self.length and ord("0") <= self.bytes[self.pos] <= ord("9"):
                    num_bytes.append(self._advance_byte())
                num_text = num_bytes.decode("ascii")
                tokens.append(Token(TokenKind.NUMBER, num_text, tok_line, tok_col))
                continue

            if (ord("a") <= b <= ord("z")) or (ord("A") <= b <= ord("Z")) or b == ord("_"):
                ident_bytes = bytearray()
                while self.pos < self.length:
                    cur = self.bytes[self.pos]
                    if (ord("a") <= cur <= ord("z")) or (ord("A") <= cur <= ord("Z")) or (ord("0") <= cur <= ord("9")) or cur == ord("_"):
                        ident_bytes.append(self._advance_byte())
                    else:
                        break
                ident_text = ident_bytes.decode("ascii")
                kind = KEYWORDS.get(ident_text, TokenKind.IDENT)
                tokens.append(Token(kind, ident_text, tok_line, tok_col))
                continue

            bad_byte = self._advance_byte()
            try:
                char_str = chr(bad_byte) if bad_byte < 128 else f"\\x{bad_byte:02x}"
            except Exception:
                char_str = f"\\x{bad_byte:02x}"
            raise LexerError(tok_line, tok_col, f"unexpected byte/character '{char_str}'")

        tokens.append(Token(TokenKind.EOF, "", self.line, self.col))
        return tokens

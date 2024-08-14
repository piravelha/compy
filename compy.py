from dataclasses import dataclass
from enum import Enum, auto
import re
from typing import Any, Callable, Generic, TypeAlias, TypeVar


TokenTypes_T = TypeVar("TokenTypes_T", bound=Enum)

@dataclass
class Location:
  file: str
  line: int
  column: int
  def __repr__(self):
    return f"{self.file}:{self.line}:{self.column}"

@dataclass
class Token(Generic[TokenTypes_T]):
  type: TokenTypes_T
  value: str
  location: Location
  def __repr__(self):
    return f"[{self.type.name}: {repr(self.value)}]"

class EOF(Token[Any]):
  def __init__(self): pass

@dataclass
class LexingError(Exception):
  def __init__(self,
               location: Location,
               message: str):
    super().__init__()
    self.location = location
    self.message = message
  def __str__(self):
    return f"{self.location}: {self.message}"

LexingResult: TypeAlias = list[Token[TokenTypes_T]] | LexingError

class Lexer(Generic[TokenTypes_T]):
  def __init__(self):
    self.regexes: dict[TokenTypes_T, str] = {}
    self.strings: dict[TokenTypes_T, str] = {}
    self.regex_skips: list[str] = []
    self.string_skips: list[str] = []

  def add_regex(self, type: TokenTypes_T, regex: str) -> None:
    regex = "^(" + regex + ")"
    self.regexes[type] = regex

  def add_str(self, type: TokenTypes_T, string: str) -> None:
    self.strings[type] = string

  def skip_regex(self, regex: str) -> None:
    regex = "^(" + regex + ")"
    self.regex_skips.append(regex)

  def skip_string(self, string: str) -> None:
    self.string_skips.append(string)

  def _increment_location(self,
                          line: int,
                          column: int,
                          whole: str
                          ) -> tuple[int, int]:
    for char in whole:
      if char == "\n":
        line += 1
        column = 1
      else:
        column += 1

    return line, column

  def _run_skips(self,
                 line: int,
                 column: int,
                 code: str
                 ) -> tuple[int, int, str]:
    while True:
      skip_matched = False

      for skip in self.regex_skips:
        m = re.match(skip, code)
        if m is None: continue
        skip_matched = True
        whole = m.group(0)
        code = code[len(whole):]
        line, column = self._increment_location(line, column, whole)

      for skip in self.string_skips:
        if not code.startswith(skip): continue
        skip_matched = True
        code = code[len(skip):]
        line, column = self._increment_location(line, column, skip)
        
      if not skip_matched: break
    return line, column, code

  def lex(self,
          file_path: str,
          code: str
          ) -> LexingResult[TokenTypes_T]:

    tokens: list[Token[TokenTypes_T]] = []
    line: int = 1
    column: int = 1

    while len(code) > 0:

      line, column, code = self._run_skips(
        line,
        column,
        code)

      if len(code) <= 0: break
      
      matched = False

      for type, regex in self.regexes.items():
        m = re.match(regex, code)
        if m is None: continue
        matched = True
        loc = Location(file_path, line, column)
        whole = m.group(0)
        code = code[len(whole):]

        line, column = self._increment_location(
          line,
          column,
          whole)
        tokens.append(Token(type, whole, loc))
        break

      for type, string in self.strings.items():
        if not code.startswith(string): continue
        matched = True
        loc = Location(file_path, line, column)
        code = code[len(string):]
        line, column = self._increment_location(line, column, string)
        tokens.append(Token(type, string, loc))
        break

      if not matched:
        loc = Location(file_path, line, column)
        return LexingError(loc, f"SYNTAX ERROR: Invalid character: '{code[0]}'")
          
    return tokens

ParserType_T = TypeVar("ParserType_T", covariant=True)
ParserType_U = TypeVar("ParserType_U", covariant=True)
ParserType_V = TypeVar("ParserType_V", covariant=True)

ParserType_Invariant = TypeVar("ParserType_Invariant")

@dataclass
class ParsingSuccess(Generic[TokenTypes_T, ParserType_T]):
  value: ParserType_T
  rest: list[Token[TokenTypes_T]]

@dataclass
class ParsingFailure(Generic[TokenTypes_T]):
  expected: list[TokenTypes_T]
  got: Token[TokenTypes_T]

ParsingResult: TypeAlias = ParsingSuccess[TokenTypes_T, ParserType_T] | ParsingFailure[TokenTypes_T]

@dataclass
class Seq(Generic[ParserType_T, ParserType_U]):
  left: ParserType_T
  right: ParserType_U

class Parser(Generic[TokenTypes_T, ParserType_T]):
  def __init__(self, parse: Callable[[list[Token[TokenTypes_T]]], ParsingResult[TokenTypes_T, ParserType_T]]) -> None:
    self.parse = parse

  def sequence_right(self, parser: 'Parser[TokenTypes_T, ParserType_U]') -> 'Parser[TokenTypes_T, ParserType_U]':
    def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_U]:
      result1 = self.parse(tokens)
      match result1:
        case ParsingFailure(exp, got):
          return ParsingFailure(exp, got)
        case ParsingSuccess(_, rest):
          result2 = parser.parse(rest)
          return result2
    return Parser(parse)
  __rshift__ = sequence_right
  def sequence_left(self, parser: 'Parser[TokenTypes_T, ParserType_U]') -> 'Parser[TokenTypes_T, ParserType_T]':
    def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_T]:
      result1 = self.parse(tokens)
      match result1:
        case ParsingFailure(exp, got):
          return ParsingFailure(exp, got)
        case ParsingSuccess(x, rest):
          result2 = parser.parse(rest)
          match result2:
            case ParsingFailure(exp, got):
              return ParsingFailure(exp, got)
            case ParsingSuccess(_, rest):
              return ParsingSuccess(x, rest)
    return Parser(parse)
  __lshift__ = sequence_left
  def sequence(self, parser: 'Parser[TokenTypes_T, ParserType_U]') -> 'SeqParser[TokenTypes_T, ParserType_T, ParserType_U]':
    def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, Seq[ParserType_T, ParserType_U]]:
      match self.parse(tokens):
        case ParsingFailure(exp, got):
          return ParsingFailure(exp, got)
        case ParsingSuccess(x, rest):
          match parser.parse(rest):
            case ParsingFailure(exp, got):
              return ParsingFailure(exp, got)
            case ParsingSuccess(y, rest):
              return ParsingSuccess(Seq(x, y), rest)
    return SeqParser(parse)
  __xor__ = sequence
  def alt(self, parser: 'Parser[TokenTypes_T, ParserType_T]') -> 'Parser[TokenTypes_T, ParserType_T]':
    def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_T]:
      match self.parse(tokens):
        case ParsingFailure(exp1, _):
          match parser.parse(tokens):
            case ParsingFailure(exp2, got):
              return ParsingFailure(exp1 + exp2, got)
            case ParsingSuccess(x, rest):
              return ParsingSuccess(x, rest)
        case ParsingSuccess(x, rest):
          return ParsingSuccess(x, rest)
    return Parser(parse)
  __or__ = alt

class SeqParser(Generic[TokenTypes_T, ParserType_T, ParserType_U], Parser[TokenTypes_T, Seq[ParserType_T, ParserType_U]]):
  def map(self, mapper: Callable[[ParserType_T, ParserType_U], ParserType_V]):
    def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_V]:
      match self.parse(tokens):
        case ParsingFailure(exp, got):
          return ParsingFailure(exp, got)
        case ParsingSuccess(Seq(a, b), rest):
          return ParsingSuccess(mapper(a, b), rest)
    return Parser(parse)

def token(type: TokenTypes_T, mapper: Callable[[str], ParserType_T]) -> Parser[TokenTypes_T, ParserType_T]:
  def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_T]:
    if len(tokens) == 0:
      return ParsingFailure([type], EOF())
    if tokens[0].type == type:
      return ParsingSuccess(mapper(tokens[0].value), tokens[1:])
    return ParsingFailure([type], tokens[1])
  return Parser(parse)

def singleton(type: TokenTypes_T, value: ParserType_Invariant) -> Parser[TokenTypes_T, ParserType_Invariant]:
  def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, ParserType_Invariant]:
    if len(tokens) == 0:
      return ParsingFailure([type], EOF())
    if tokens[0].type == type:
      return ParsingSuccess(value, tokens[1:])
    return ParsingFailure([type], tokens[0])
  return Parser(parse)

def lazy(parser_fn: Callable[[], Parser[TokenTypes_T, ParserType_T]]) -> Parser[TokenTypes_T, ParserType_T]:
  def parse(tokens: list[Token[TokenTypes_T]]):
    return parser_fn().parse(tokens)
  return Parser(parse)

def ignore(type: TokenTypes_T) -> Parser[TokenTypes_T, None]:
  def parse(tokens: list[Token[TokenTypes_T]]) -> ParsingResult[TokenTypes_T, None]:
    if len(tokens) == 0:
      return ParsingFailure([type], EOF())
    if tokens[0].type == type:
      return ParsingSuccess(None, tokens[1:])
    return ParsingFailure([type], tokens[0])
  return Parser(parse)

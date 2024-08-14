
from typing import Union
from compy import *

class TokenType(Enum):
  Int = auto()
  Plus = auto()
  Times = auto()
  LeftParen = auto()
  RightParen = auto()

lexer = Lexer[TokenType]()
lexer.add_regex(TokenType.Int, r"\d+")
lexer.add_str(TokenType.Plus, "+")
lexer.add_str(TokenType.Times, "*")
lexer.add_str(TokenType.LeftParen, "(")
lexer.add_str(TokenType.RightParen, ")")
lexer.skip_regex(r"\s+")

ExprNode: TypeAlias = Union[
  'IntNode', 'PlusNode', 'TimesNode']

@dataclass
class IntNode:
  value: str

@dataclass
class TimesNode:
  left: ExprNode
  right: ExprNode

@dataclass
class PlusNode:
  left: ExprNode
  right: ExprNode

def int_node(n: str) -> ExprNode: return IntNode(n)
def plus_node(l: ExprNode, r: ExprNode) -> ExprNode:
  return PlusNode(l, r)
def times_node(l: ExprNode, r: ExprNode) -> ExprNode:
  return TimesNode(l, r)


expr_parser: Parser[TokenType, ExprNode] = lazy(
  lambda: plus_parser | term_parser
)

int_parser = token(TokenType.Int, int_node)

atom_parser = int_parser | (
  ignore(TokenType.LeftParen)
    >> expr_parser
    << ignore(TokenType.RightParen)
)

times_parser = lazy(lambda: (
  (atom_parser << ignore(TokenType.Times))
    ^ atom_parser
).map(times_node))

term_parser = (
  times_parser | atom_parser
)

plus_parser = lazy(lambda: (
  (term_parser << ignore(TokenType.Plus))
    ^ term_parser
).map(plus_node))

def eval_expr(node: ExprNode) -> int:
  match node:
    case IntNode(n): return int(n)
    case TimesNode(l, r):
      return eval_expr(l) * eval_expr(r)
    case PlusNode(l, r):
      return eval_expr(l) + eval_expr(r)

code = "1 * (2 + 3)"
lexing_result = lexer.lex("<stdin>", code)
match lexing_result:
  case LexingError():
    print(lexing_result)
    exit(1)
  case _: pass
match expr_parser.parse(lexing_result):
  case ParsingSuccess(value, rest):
    print(f"SUCCESS: {value}")
    print(f"RESULT: {eval_expr(value)}")
  case ParsingFailure(exp, got):
    print(f"FAILURE: Expected {exp}, got {got}")



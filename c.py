from compy import *

def to_c_name(name: str) -> str:
  new = ""
  for char in name:
    if char.isalpha(): new += char
    elif char == "_": new += char
    else: new += f"_{ord(char)}"
  return new

@dataclass
class C_Identifier:
  name: str
  def __init__(self, name: str):
    self.name = to_c_name(name)
  @property
  def as_code(self) -> str:
    return self.name

ident = C_Identifier("lisp-name")
print(ident.as_code)

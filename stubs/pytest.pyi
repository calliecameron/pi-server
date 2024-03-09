from collections.abc import Callable
from typing import Any, TypeVar

from _pytest.mark import structures

_F = TypeVar("_F", bound=Callable[..., Any])

mark: structures.MarkGenerator

def fixture(scope: str = "function", autouse: bool = False) -> Callable[[_F], _F]: ...
def fail(msg: str) -> None: ...

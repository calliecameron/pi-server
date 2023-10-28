from typing import Any, Callable, TypeVar

from _pytest.mark import structures

F = TypeVar("F", bound=Callable[..., Any])

mark: structures.MarkGenerator

def fixture(scope: str = "function", autouse: bool = False) -> Callable[[F], F]: ...
def fail(msg: str) -> None: ...

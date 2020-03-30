from typing import Any, Callable, TypeVar


F = TypeVar('F', bound=Callable[..., Any])


def fixture(scope: str = 'function', autouse: bool = False) -> Callable[[F], F]: ...
def fail(msg: str) -> None: ...

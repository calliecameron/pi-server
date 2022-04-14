from typing import Any, Callable, Dict, List, Tuple, TypeVar
from _pytest.mark import structures


F = TypeVar('F', bound=Callable[..., Any])


def fixture(scope: str = 'function', autouse: bool = False) -> Callable[[F], F]: ...
def fail(msg: str) -> None: ...


mark: structures.MarkGenerator

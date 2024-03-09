from collections.abc import Callable
from contextlib import ContextDecorator
from dataclasses import dataclass

from typing_extensions import Self

@dataclass
class Timer(ContextDecorator):
    name: str | None
    text: str
    logger: Callable[[str], None] | None
    last: float
    def __init__(
        self,
        name: str | None = None,
        text: str = "",
        logger: Callable[[str], None] | None = ...,
    ) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc_info: object) -> None: ...

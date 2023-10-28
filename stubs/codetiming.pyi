from contextlib import ContextDecorator
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass
class Timer(ContextDecorator):
    name: Optional[str]
    text: str
    logger: Optional[Callable[[str], None]]
    last: float
    def __init__(
        self,
        name: Optional[str] = None,
        text: str = "",
        logger: Optional[Callable[[str], None]] = print,
    ) -> None: ...
    def __enter__(self) -> Timer: ...
    def __exit__(self, *exc_info: Any) -> None: ...

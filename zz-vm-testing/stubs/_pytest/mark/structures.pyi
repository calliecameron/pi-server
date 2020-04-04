from typing import Any, Dict, Tuple

class Mark:
    name: str
    kwargs: Dict[str, Tuple[str, ...]]

class MarkDecorator:
    def __call__(self, *args: Any, **kwargs: Any) -> MarkDecorator: ...

class MarkGenerator:
    def __getattr__(self, name: str) -> MarkDecorator: ...

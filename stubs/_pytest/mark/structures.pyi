from typing import Any

class Mark:
    name: str
    kwargs: dict[str, tuple[str, ...]]

class MarkDecorator:
    def __call__(self, *args: Any, **kwargs: Any) -> MarkDecorator: ...  # noqa: ANN401

class MarkGenerator:
    def __getattr__(self, name: str) -> MarkDecorator: ...

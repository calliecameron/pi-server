from typing import Any

class Sudo:
    def __enter__(self) -> Sudo: ...
    def __exit__(self, *exc_info: Any) -> None: ...
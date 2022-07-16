from typing import List


class File:
    path: str
    exists: bool
    content: bytes
    content_string: str
    user: str
    group: str
    mode: int
    def check_output(self, cmd: str) -> None: ...
    def write(self, content: str) -> None: ...
    def clear(self) -> None: ...
    def listdir(self) -> List[str]: ...

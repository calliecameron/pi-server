from typing import NamedTuple

class Status(NamedTuple):
    name: str
    state: str
    provider: str

class Vagrant:
    RUNNING: str
    def status(self) -> list[Status]: ...
    def up(self, vm_name: str) -> None: ...
    def halt(self, vm_name: str) -> None: ...

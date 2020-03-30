from typing import List, NamedTuple

Status = NamedTuple('Status', [('name', str), ('state', str), ('provider', str)])


class Vagrant:
    RUNNING: str
    def status(self) -> List[Status]: ...
    def up(self, vm_name: str) -> None: ...
    def halt(self, vm_name: str) -> None: ...

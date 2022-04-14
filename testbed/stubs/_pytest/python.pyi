from typing import Optional, Sequence
from _pytest.mark.structures import Mark


class FunctionDefinition:
    def get_closest_marker(self, name: str) -> Optional[Mark]: ...


class Metafunc:
    definition: FunctionDefinition
    def parametrize(self, argnames: str, arvalues: Sequence[str]) -> None: ...

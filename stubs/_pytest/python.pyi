from collections.abc import Sequence

from _pytest.mark.structures import Mark

class FunctionDefinition:
    def get_closest_marker(self, name: str) -> Mark | None: ...

class Metafunc:
    definition: FunctionDefinition
    def parametrize(self, argnames: str, arvalues: Sequence[str]) -> None: ...

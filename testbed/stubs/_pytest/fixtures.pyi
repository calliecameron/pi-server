from typing import Dict, List
from _pytest.mark import structures

class FixtureRequest:
    keywords: Dict[str, List[structures.Mark]]

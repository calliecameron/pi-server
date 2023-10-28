from _pytest.mark import structures

class FixtureRequest:
    keywords: dict[str, list[structures.Mark]]

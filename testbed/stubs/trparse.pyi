from typing import List


class Probe:
    annotation: str
    ip: str

class Hop:
    probes: List[Probe]

class Traceroute:
    hops: List[Hop]


def loads(data: str) -> Traceroute: ...

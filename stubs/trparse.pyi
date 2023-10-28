class Probe:
    annotation: str
    ip: str

class Hop:
    probes: list[Probe]

class Traceroute:
    hops: list[Hop]

def loads(data: str) -> Traceroute: ...

from testinfra.modules.addr import Addr

class Host:
    def addr(self, addr: str) -> Addr: ...

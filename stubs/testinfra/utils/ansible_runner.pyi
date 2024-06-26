from testinfra.host import Host

class AnsibleRunner:
    def __init__(self, inventory: str) -> None: ...
    def get_hosts(self) -> list[str]: ...
    def get_host(self, name: str, ssh_config: str) -> Host: ...

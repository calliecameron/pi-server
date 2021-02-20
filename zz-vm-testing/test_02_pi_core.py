from typing import Dict
from testinfra.host import Host
from conftest import for_host_types


class Test02PiCore:
    @for_host_types('pi')
    def test_00_packages(self, hostname: str, hosts: Dict[str, Host]) -> None:
        # We pick one of the packages that the script installs, that isn't installed by default.
        assert hosts[hostname].package('ntfs-3g').is_installed

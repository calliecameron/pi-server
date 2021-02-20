from typing import Dict
from testinfra.host import Host
from conftest import for_host_types, host_number


class Test02PiCore:
    @for_host_types('pi')
    def test_00_packages(self, hostname: str, hosts: Dict[str, Host]) -> None:
        # We pick one of the packages that the script installs, that isn't installed by default.
        assert hosts[hostname].package('ntfs-3g').is_installed

    @for_host_types('pi')
    def test_01_vars(self, hostname: str, hosts: Dict[str, Host], masks: Dict[str, str]) -> None:
        host = hosts[hostname]
        assert (host.file('/etc/pi-server/lan-network-addr').content_string.strip()
                == masks['lan' + host_number(hostname)])
        assert (host.file('/etc/pi-server/vpn-network-addr').content_string.strip()
                == masks['pi%s_vpn' % host_number(hostname)])
        assert host.file('/etc/pi-server/storage-drive-dev').content_string.strip() == '/dev/sdb'
        assert host.file('/etc/pi-server/storage-data-partition').content_string.strip() == '1'
        assert host.file('/etc/pi-server/storage-backup-partition').content_string.strip() == '2'
        assert host.file('/etc/pi-server/storage-spinning-disk').content_string.strip() == 'n'

    @for_host_types('pi')
    def test_02_firewall(self, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        assert host.file('/etc/pi-server/firewall/allow-forwarding').exists

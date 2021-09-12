from typing import Dict
from urllib.parse import urlparse
from testinfra.host import Host
from conftest import for_host_types, WebDriver


class TestSyncthing:
    @for_host_types('pi')
    def test_syncthing(self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        # For now we just do some basic checks
        host = hosts[hostname]
        assert host.service('pi-server-syncthing').is_enabled
        assert host.service('pi-server-syncthing').is_running
        assert host.process.filter(user='www-data', comm='syncthing')

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                link = driver.find_element_by_link_text('Syncthing control panel')
                assert urlparse(link.get_attribute('href')).hostname == this_addr

        test(addrs[hostname])
        test(hostname + '.local')

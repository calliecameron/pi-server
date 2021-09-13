from typing import Dict
from urllib.parse import urlparse
from testinfra.host import Host
from conftest import for_host_types, WebDriver


class TestMediaServer:
    @for_host_types('pi')
    def test_media_server(
            self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        # For now we just do some basic checks
        host = hosts[hostname]
        assert host.service('minidlna').is_enabled
        assert host.service('minidlna').is_running
        assert host.process.filter(user='www-data', comm='minidlnad')

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                link = driver.find_element_by_link_text('Media server status')
                assert urlparse(link.get_attribute('href')).hostname == this_addr

        test(addrs[hostname])
        test(hostname + '.local')

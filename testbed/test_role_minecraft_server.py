from typing import Dict
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from conftest import for_host_types, WebDriver


class TestRoleMinecraftServer:

    @for_host_types('ubuntu')
    def test_site(
            self,
            hostname: str,
            addrs: Dict[str, str]) -> None:
        this_addr = addrs[hostname]

        with WebDriver() as driver:
            driver.get('http://' + this_addr)
            assert driver.title == 'Minecraft'
            link = driver.find_element(by=By.LINK_TEXT, value='Current world')
            assert urlparse(link.get_attribute('href')).hostname == this_addr
            driver.click(link)

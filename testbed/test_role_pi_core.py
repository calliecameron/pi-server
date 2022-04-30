import time
from typing import Dict
from urllib.parse import urlparse
import requests
from testinfra.host import Host
from selenium.webdriver.common.by import By
from conftest import for_host_types, MockServer, WebDriver, Vagrant


class TestRolePiCore:

    @for_host_types('pi')
    def test_avahi(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        addrs = host.check_output(
            'ip a | grep "inet " | cut "-d " -f 6 | sed "s|/.*||g"').strip().split('\n')
        addr = host.check_output(
            f'getent ahostsv4 "{hostname}.local" | head -n 1 | cut "-d " -f 1')
        assert addr in addrs

    @for_host_types('pi')
    def test_zoneedit(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            mockserver: MockServer) -> None:
        host = hosts[hostname]
        service = host.service('pi-server-cron-zoneedit')
        journal = host.journal()
        auth_header = requests.Request()
        requests.auth.HTTPBasicAuth('foo', 'bar')(auth_header)

        zoneedit_req = {
            'httpRequest': {
                'method': 'GET',
                'path': '/auth/dynamic.html',
                'queryStringParameters': {
                    'host': [hostname + '.testbed'],
                },
                'headers': [
                    {
                        'name': 'Authorization',
                        'values': [auth_header.headers['Authorization']],
                    },
                ],
                'secure': True,
            },
            'httpResponse': {
                'statusCode': 200,
            },
        }

        with host.shadow_file('/etc/pi-server/zoneedit/username.txt') as username_file, \
                host.shadow_file('/etc/pi-server/zoneedit/password.txt') as password_file:

            # No username or password, no request
            journal.clear()
            mockserver.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/pi-server-zoneedit'):
                pass
            mockserver.assert_not_called()

            assert not service.is_running
            log = journal.entries('pi-server-cron-zoneedit')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Updated ZoneEdit') == 0
            assert log.count(r'Not running.*') == 1
            assert log.count(r'.*ZoneEdit update failed') == 0

            # Correct username/password, manual run
            with host.sudo():
                username_file.write('foo')
                password_file.write('bar')

            journal.clear()
            mockserver.clear()
            mockserver.expect(zoneedit_req)
            with host.sudo():
                host.check_output('systemctl start --wait pi-server-cron-zoneedit')
            mockserver.assert_called()

            assert not service.is_running
            log = journal.entries('pi-server-cron-zoneedit')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Updated ZoneEdit') == 1
            assert log.count(r'Not running.*') == 0
            assert log.count(r'.*ZoneEdit update failed') == 0

            # Correct username/password at net up
            journal.clear()
            mockserver.clear()
            mockserver.expect(zoneedit_req)
            with host.sudo():
                host.check_output('ip link set enp0s8 down')
                host.check_output('ip link set enp0s8 up')
            time.sleep(65)
            mockserver.assert_called()

            assert not service.is_running
            log = journal.entries('pi-server-cron-zoneedit')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Updated ZoneEdit') == 1
            assert log.count(r'Not running.*') == 0
            assert log.count(r'.*ZoneEdit update failed') == 0

            # Correct username/password in cronjob
            journal.clear()
            mockserver.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
                pass
            mockserver.assert_called()

            assert not service.is_running
            log = journal.entries('pi-server-cron-zoneedit')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Updated ZoneEdit') == 1
            assert log.count(r'Not running.*') == 0
            assert log.count(r'.*ZoneEdit update failed') == 0

            # Wrong password in cronjob
            with host.sudo():
                password_file.write('baz')
            journal.clear()
            mockserver.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
                pass
            mockserver.assert_not_called()

            assert not service.is_running
            log = journal.entries('pi-server-cron-zoneedit')
            assert log.count(r'.*ERROR.*') == 1
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 2
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 0
            assert log.count(r'Updated ZoneEdit') == 0
            assert log.count(r'Not running.*') == 0
            assert log.count(r'.*ZoneEdit update failed') == 1

    @for_host_types('pi')
    def test_control_panel(
            self,
            hostname: str,
            addrs: Dict[str, str]) -> None:

        def test(this_addr: str, other_addr: str) -> None:
            # Test that the main page links to the other address
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                driver.validate_html()
                other_links = driver.validate_links()
                assert len(other_links) == 1 and list(other_links)[0].hostname == other_addr

            # Test that traefik is routing properly by loading some other path
            with WebDriver() as driver:
                driver.get('http://' + this_addr + '/prometheus')
                driver.validate_html()

        addr = addrs[hostname]
        local = hostname + '.local'
        test(addr, local)
        test(local, addr)

    @for_host_types('pi')
    def test_shutdownd(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            vagrant: Vagrant) -> None:
        host = hosts[hostname]
        path = '/tmp/disappear-on-reboot'

        def test(this_addr: str) -> None:
            def navigate_and_click(text: str) -> None:
                host.file(path).write('')
                with WebDriver() as driver:
                    driver.get('http://' + this_addr)

                    link = driver.find_element(by=By.LINK_TEXT, value=text)
                    assert urlparse(link.get_attribute('href')).hostname == this_addr
                    driver.click(link)
                    driver.validate_html()
                    other_links = driver.validate_links()
                    assert not other_links

                    button = driver.find_element(by=By.NAME, value='btn')
                    driver.click(button)
                    driver.validate_html()
                    other_links = driver.validate_links()
                    assert not other_links

            navigate_and_click('Restart')
            time.sleep(40)
            vagrant.rescan_state()
            assert vagrant.state()[hostname]
            assert not host.file(path).exists

            navigate_and_click('Shut down')
            time.sleep(40)
            vagrant.rescan_state()
            assert not vagrant.state()[hostname]
            vagrant.reboot(hostname)
            assert vagrant.state()[hostname]
            assert not host.file(path).exists

        test(addrs[hostname])
        test(hostname + '.local')

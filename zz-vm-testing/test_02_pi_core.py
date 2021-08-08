import time
from typing import Any, Dict, List, cast
from urllib.parse import urlparse
import requests
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from testinfra.host import Host
from tidylib import tidy_document

from conftest import for_host_types, host_number, Email, MockServer


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

    @for_host_types('pi')
    def test_03_dynamic_dns(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email,
            mockserver: MockServer) -> None:
        host = hosts[hostname]

        # Part 1 - avahi
        assert (host.check_output('getent hosts %s.local' % hostname) ==
                '%s       %s.local' % (addrs[hostname], hostname))

        # Part 2 - zoneedit
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

        with host.shadow_file('/etc/pi-server/zoneedit/zoneedit-username') as username_file, \
             host.shadow_file('/etc/pi-server/zoneedit/zoneedit-password') as password_file, \
             host.disable_login_emails():

            # No username or password, no request or emails
            mockserver.clear()
            email.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
                pass
            mockserver.assert_not_called()
            time.sleep(15)
            email.assert_emails([], only_from=hostname)

            # Correct username/password, manual run
            with host.sudo():
                username_file.write('foo')
                password_file.write('bar')

            mockserver.clear()
            email.clear()
            mockserver.expect(zoneedit_req)
            with host.sudo():
                host.check_output('/etc/pi-server/zoneedit/zoneedit-update')
            mockserver.assert_called()
            time.sleep(15)
            email.assert_emails([], only_from=hostname)

            # Correct username/password in cronjob
            mockserver.clear()
            email.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
                pass
            mockserver.assert_called()
            time.sleep(15)
            email.assert_emails([], only_from=hostname)

            # Wrong password in cronjob
            with host.sudo():
                password_file.write('baz')
            mockserver.clear()
            email.clear()
            mockserver.expect(zoneedit_req)
            with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
                pass
            mockserver.assert_not_called()
            time.sleep(15)
            email.assert_emails([
                {
                    'from': '',
                    'to': '',
                    'subject': ('Cron <root@%s>    cd / && run-parts --report /etc/cron.hourly'
                                % hostname),
                    'body_re': (r'/etc/cron.hourly/zoneedit-update:\n'
                                r'ZoneEdit update failed; check the log file\n'),
                },
            ], only_from=hostname)

    @for_host_types('pi')
    def test_04_nginx(
            self,
            hostname: str,
            addrs: Dict[str, str]) -> None:

        def test(this_addr: str, other_addr: str) -> None:
            with Firefox() as driver:
                def elems(tag: str) -> List[Any]:
                    e = cast(List[Any], driver.find_elements(By.TAG_NAME, tag))
                    assert e
                    return e

                driver.get('http://' + this_addr)

                for e in elems('link'):
                    assert urlparse(e.get_attribute('href')).hostname == this_addr

                for e in elems('img'):
                    assert urlparse(e.get_attribute('src')).hostname == this_addr

                same = set()
                other = set()
                for e in elems('a'):
                    href = e.get_attribute('href')
                    if urlparse(href).hostname == this_addr:
                        same.add(href)
                    else:
                        other.add(href)
                assert len(same) > 1
                assert len(other) == 1 and urlparse(list(other)[0]).hostname == other_addr

            r = requests.get('http://' + this_addr)
            r.raise_for_status()
            errors = tidy_document(r.text, options={'show-warnings':0})[1]
            assert not errors

        addr = addrs[hostname]
        local = hostname + '.local'
        test(addr, local)
        test(local, addr)

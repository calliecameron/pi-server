import time
from typing import Dict, List
from urllib.parse import urlparse
import requests
from testinfra.host import Host
from conftest import for_host_types, host_number, Email, MockServer, WebDriver, Vagrant


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
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                driver.validate_html()
                other_links = driver.validate_links()
                assert len(other_links) == 1 and list(other_links)[0].hostname == other_addr

        addr = addrs[hostname]
        local = hostname + '.local'
        test(addr, local)
        test(local, addr)

    @for_host_types('pi')
    def test_05_shutdownd(
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
                    link = driver.find_element_by_link_text(text)

                    assert urlparse(link.get_attribute('href')).hostname == this_addr

                    link.click()
                    driver.validate_html()
                    other_links = driver.validate_links()
                    assert not other_links
                    button = driver.find_element_by_name('btn')

                    button.click()
                    driver.validate_html()
                    other_links = driver.validate_links()
                    assert not other_links

            navigate_and_click('Restart')
            time.sleep(20)
            vagrant.rescan_state()
            assert vagrant.state()[hostname]
            assert not host.file(path).exists

            navigate_and_click('Shut down')
            time.sleep(10)
            vagrant.rescan_state()
            assert not vagrant.state()[hostname]
            vagrant.reboot(hostname)
            assert vagrant.state()[hostname]
            assert not host.file(path).exists

        test(addrs[hostname])
        test(hostname + '.local')

    @for_host_types('pi')
    def test_06_storage_drives(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            email: Email) -> None:
        host = hosts[hostname]

        # Part 1 - fstab
        data = host.mount_point('/mnt/data')
        assert data.exists
        assert data.filesystem == 'ext4'
        assert data.device == '/dev/sdb1'

        backup = host.mount_point('/mnt/backup')
        assert not backup.exists

        try:
            with host.sudo():
                host.check_output('mount /mnt/backup')

            backup = host.mount_point('/mnt/backup')
            assert backup.exists
            assert backup.filesystem == 'ext4'
            assert backup.device == '/dev/sdb2'
        finally:
            with host.sudo():
                host.check_output('umount /mnt/backup')

        # Part 2 - disk space checking
        with host.disable_login_emails():
            # Lots of space
            email.clear()
            with host.run_crons():
                pass

            email.assert_emails([], only_from=hostname)

            # Not much space
            try:
                data_file = '/mnt/data/bigfile'
                backup_file = '/mnt/backup/bigfile'
                with host.sudo():
                    host.make_bigfile(data_file, '/mnt/data')
                    host.check_output('mount /mnt/backup')
                    host.make_bigfile(backup_file, '/mnt/backup')
                    host.check_output('umount /mnt/backup')

                email.clear()
                with host.run_crons():
                    pass

                email.assert_emails([{
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] Storage space alert' % hostname,
                    'body_re': (r'A partition is above 90% full.\n(.*\n)*'
                                r'/dev/sdb2.*9[0-9]%.*/mnt/backup\n(.*\n)*'),
                }, {
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] Storage space alert' % hostname,
                    'body_re': (r'A partition is above 90% full.\n(.*\n)*'
                                r'/dev/sdb1.*9[0-9]%.*/mnt/data\n(.*\n)*'),
                }], only_from=hostname)
            finally:
                with host.sudo():
                    host.check_output('rm -f %s' % data_file)
                    host.check_output('mount /mnt/backup')
                    host.check_output('rm -f %s' % backup_file)
                    host.check_output('umount /mnt/backup')

            # Lots of space again
            email.clear()
            with host.run_crons():
                pass

            email.assert_emails([], only_from=hostname)

    @for_host_types('pi')
    def test_07_storage_directories(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]

        assert host.file('/mnt/data/pi-server-data/config').exists
        assert host.file('/mnt/data/pi-server-data/config').user == 'root'
        assert host.file('/mnt/data/pi-server-data/config').group == 'root'

        assert host.file('/mnt/data/pi-server-data/data').exists
        assert host.file('/mnt/data/pi-server-data/data').user == 'www-data'
        assert host.file('/mnt/data/pi-server-data/data').group == 'www-data'

        assert host.file('/mnt/data/pi-server-data/data-no-backups').exists
        assert host.file('/mnt/data/pi-server-data/data-no-backups').user == 'www-data'
        assert host.file('/mnt/data/pi-server-data/data-no-backups').group == 'www-data'

        assert host.file('/mnt/data/scratch').exists
        assert host.file('/mnt/data/scratch').user == 'vagrant'
        assert host.file('/mnt/data/scratch').group == 'vagrant'

        try:
            with host.sudo():
                host.check_output('mount /mnt/backup')

            assert host.file('/mnt/backup/pi-server-backup/main').exists
            assert host.file('/mnt/backup/pi-server-backup/main').user == 'root'
            assert host.file('/mnt/backup/pi-server-backup/main').group == 'root'

            assert host.file('/mnt/backup/pi-server-backup/git').exists
            assert host.file('/mnt/backup/pi-server-backup/git').user == 'www-data'
            assert host.file('/mnt/backup/pi-server-backup/git').group == 'www-data'

            assert host.file('/mnt/backup/pi-server-backup/email').exists
            assert host.file('/mnt/backup/pi-server-backup/email').user == 'root'
            assert host.file('/mnt/backup/pi-server-backup/email').group == 'root'
        finally:
            with host.sudo():
                host.check_output('umount /mnt/backup')

import os.path
import time
from typing import Dict, List, Set
from urllib.parse import urlparse
import requests
from testinfra.host import Host
from testinfra.modules.file import File
from conftest import for_host_types, host_number, Email, MockServer, WebDriver, Vagrant


class Test02PiCore:

    # @for_host_types('pi')
    # def test_02_firewall(self, hostname: str, hosts: Dict[str, Host]) -> None:
    #     host = hosts[hostname]
    #     assert host.file('/etc/pi-server/firewall/allow-forwarding').exists

    # @for_host_types('pi')
    # def test_03_dynamic_dns(
    #         self,
    #         hostname: str,
    #         hosts: Dict[str, Host],
    #         addrs: Dict[str, str],
    #         email: Email,
    #         mockserver: MockServer) -> None:
    #     host = hosts[hostname]

    #     # Part 1 - avahi
    #     assert (host.check_output('getent ahostsv4 %s.local | head -n 1' % hostname) ==
    #             '%s       STREAM %s.local' % (addrs[hostname], hostname))

    #     # Part 2 - zoneedit
    #     auth_header = requests.Request()
    #     requests.auth.HTTPBasicAuth('foo', 'bar')(auth_header)

    #     zoneedit_req = {
    #         'httpRequest': {
    #             'method': 'GET',
    #             'path': '/auth/dynamic.html',
    #             'queryStringParameters': {
    #                 'host': [hostname + '.testbed'],
    #             },
    #             'headers': [
    #                 {
    #                     'name': 'Authorization',
    #                     'values': [auth_header.headers['Authorization']],
    #                 },
    #             ],
    #             'secure': True,
    #         },
    #         'httpResponse': {
    #             'statusCode': 200,
    #         },
    #     }

    #     with host.shadow_file('/etc/pi-server/zoneedit/zoneedit-username') as username_file, \
    #          host.shadow_file('/etc/pi-server/zoneedit/zoneedit-password') as password_file, \
    #          host.disable_login_emails():

    #         # No username or password, no request or emails
    #         mockserver.clear()
    #         email.clear()
    #         mockserver.expect(zoneedit_req)
    #         with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
    #             pass
    #         mockserver.assert_not_called()
    #         time.sleep(15)
    #         email.assert_emails([], only_from=hostname)

    #         # Correct username/password, manual run
    #         with host.sudo():
    #             username_file.write('foo')
    #             password_file.write('bar')

    #         mockserver.clear()
    #         email.clear()
    #         mockserver.expect(zoneedit_req)
    #         with host.sudo():
    #             host.check_output('/etc/pi-server/zoneedit/zoneedit-update')
    #         mockserver.assert_called()
    #         time.sleep(15)
    #         email.assert_emails([], only_from=hostname)

    #         # Correct username/password in cronjob
    #         mockserver.clear()
    #         email.clear()
    #         mockserver.expect(zoneedit_req)
    #         with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
    #             pass
    #         mockserver.assert_called()
    #         time.sleep(15)
    #         email.assert_emails([], only_from=hostname)

    #         # Wrong password in cronjob
    #         with host.sudo():
    #             password_file.write('baz')
    #         mockserver.clear()
    #         email.clear()
    #         mockserver.expect(zoneedit_req)
    #         with host.run_crons('00:16:50', '/bin/bash /etc/cron.hourly/zoneedit-update'):
    #             pass
    #         mockserver.assert_not_called()
    #         time.sleep(15)
    #         email.assert_emails([
    #             {
    #                 'from': '',
    #                 'to': '',
    #                 'subject': ('Cron <root@%s>    cd / && run-parts --report /etc/cron.hourly'
    #                             % hostname),
    #                 'body_re': (r'/etc/cron.hourly/zoneedit-update:\n'
    #                             r'ZoneEdit update failed; check the log file\n'),
    #             },
    #         ], only_from=hostname)

    @for_host_types('pi')
    def test_main_site(
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
            time.sleep(20)
            vagrant.rescan_state()
            assert not vagrant.state()[hostname]
            vagrant.reboot(hostname)
            assert vagrant.state()[hostname]
            assert not host.file(path).exists

        test(addrs[hostname])
        test(hostname + '.local')

    # @for_host_types('pi')
    # def test_06_storage_drives(
    #         self,
    #         hostname: str,
    #         hosts: Dict[str, Host],
    #         email: Email) -> None:
    #     host = hosts[hostname]

    #     # Part 1 - fstab
    #     data = host.mount_point('/mnt/data')
    #     assert data.exists
    #     assert data.filesystem == 'ext4'
    #     assert data.device == '/dev/sdc1'

    #     backup = host.mount_point('/mnt/backup')
    #     assert not backup.exists

    #     with host.mount_backup_dir():
    #         backup = host.mount_point('/mnt/backup')
    #         assert backup.exists
    #         assert backup.filesystem == 'ext4'
    #         assert backup.device == '/dev/sdc2'

    #     # Part 2 - disk space checking
    #     with host.disable_login_emails():
    #         # Lots of space
    #         email.clear()
    #         with host.run_crons():
    #             pass

    #         email.assert_emails([], only_from=hostname)

    #         # Not much space
    #         try:
    #             data_file = '/mnt/data/bigfile'
    #             backup_file = '/mnt/backup/bigfile'
    #             with host.sudo():
    #                 host.make_bigfile(data_file, '/mnt/data')
    #                 with host.mount_backup_dir():
    #                     host.make_bigfile(backup_file, '/mnt/backup')

    #             email.clear()
    #             with host.run_crons():
    #                 pass

    #             email.assert_emails([{
    #                 'from': 'notification@%s.testbed' % hostname,
    #                 'to': 'fake@fake.testbed',
    #                 'subject': '[%s] Storage space alert' % hostname,
    #                 'body_re': (r'A partition is above 90% full.\n(.*\n)*'
    #                             r'/dev/sdc2.*9[0-9]%.*/mnt/backup\n(.*\n)*'),
    #             }, {
    #                 'from': 'notification@%s.testbed' % hostname,
    #                 'to': 'fake@fake.testbed',
    #                 'subject': '[%s] Storage space alert' % hostname,
    #                 'body_re': (r'A partition is above 90% full.\n(.*\n)*'
    #                             r'/dev/sdc1.*9[0-9]%.*/mnt/data\n(.*\n)*'),
    #             }], only_from=hostname)
    #         finally:
    #             with host.sudo():
    #                 host.check_output('rm -f %s' % data_file)
    #                 with host.mount_backup_dir():
    #                     host.check_output('rm -f %s' % backup_file)

    #         # Lots of space again
    #         email.clear()
    #         with host.run_crons():
    #             pass

    #         email.assert_emails([], only_from=hostname)

    # @for_host_types('pi')
    # def test_07_storage_directories(
    #         self,
    #         hostname: str,
    #         hosts: Dict[str, Host]) -> None:
    #     host = hosts[hostname]

    #     assert host.file('/mnt/data/pi-server-data/config').exists
    #     assert host.file('/mnt/data/pi-server-data/config').user == 'root'
    #     assert host.file('/mnt/data/pi-server-data/config').group == 'root'

    #     assert host.file('/mnt/data/pi-server-data/data').exists
    #     assert host.file('/mnt/data/pi-server-data/data').user == 'www-data'
    #     assert host.file('/mnt/data/pi-server-data/data').group == 'www-data'

    #     assert host.file('/mnt/data/pi-server-data/data-no-backups').exists
    #     assert host.file('/mnt/data/pi-server-data/data-no-backups').user == 'www-data'
    #     assert host.file('/mnt/data/pi-server-data/data-no-backups').group == 'www-data'

    #     assert host.file('/mnt/data/scratch').exists
    #     assert host.file('/mnt/data/scratch').user == 'vagrant'
    #     assert host.file('/mnt/data/scratch').group == 'vagrant'

    #     with host.mount_backup_dir():
    #         assert host.file('/mnt/backup/pi-server-backup/main').exists
    #         assert host.file('/mnt/backup/pi-server-backup/main').user == 'root'
    #         assert host.file('/mnt/backup/pi-server-backup/main').group == 'root'

    #         assert host.file('/mnt/backup/pi-server-backup/git').exists
    #         assert host.file('/mnt/backup/pi-server-backup/git').user == 'www-data'
    #         assert host.file('/mnt/backup/pi-server-backup/git').group == 'www-data'

    #         assert host.file('/mnt/backup/pi-server-backup/email').exists
    #         assert host.file('/mnt/backup/pi-server-backup/email').user == 'root'
    #         assert host.file('/mnt/backup/pi-server-backup/email').group == 'root'

    # @for_host_types('pi')
    # def test_08_openvpn_server(self, hostname: str, hosts: Dict[str, Host]) -> None:
    #     """This just installs the openvpn service, not any configs."""
    #     host = hosts[hostname]
    #     assert host.service('openvpn').is_enabled
    #     assert host.service('openvpn').is_running

    # @for_host_types('pi')
    # def test_09_backup(
    #         self,
    #         hostname: str,
    #         hosts: Dict[str, Host],
    #         addrs: Dict[str, str],
    #         email: Email) -> None:
    #     host = hosts[hostname]
    #     backup_root = '/mnt/backup/pi-server-backup'
    #     backup_main_root = os.path.join(backup_root, 'main')
    #     backup_git_root = os.path.join(backup_root, 'git')
    #     data_root = '/mnt/data/pi-server-data/data'
    #     config_root = '/mnt/data/pi-server-data/config'

    #     def main_backup_file(path: File, backup: str) -> File:
    #         return host.file(
    #             '%s/%s/%s%s' % (backup_main_root, backup, hostname, path.path))

    #     def clear_backups() -> None:
    #         with host.mount_backup_dir():
    #             with host.sudo():
    #                 host.check_output('rm -rf %s/*' % backup_main_root)
    #                 host.check_output('rm -rf %s/*' % backup_git_root)
    #                 host.check_output('rm -f %s/last-run-date.txt' % backup_root)

    #     with host.disable_login_emails(), \
    #          host.shadow_file(os.path.join(data_root, 'foo.txt')) as data_file, \
    #          host.shadow_file(os.path.join(config_root, 'foo.txt')) as config_file, \
    #          host.shadow_file(
    #              os.path.join(
    #                  data_root, '%s-backup-config' % hostname,
    #                  'git-backup-configuration.txt')) as git_config_file:
    #         clear_backups()

    #         # Part 1 - data backups
    #         # Daily backups happen every day, weekly backups happen on Mondays, and monthly backups
    #         # happen on the first day of the month. So we test the following dates:
    #         #   - 2021/05/30 (Sun): daily only
    #         #   - 2021/05/31 (Mon): daily and weekly
    #         #   - 2021/06/01 (Tue): daily and monthly
    #         #   - 2021/06/02 (Wed): daily only

    #         def check_main(backup: str, s: str) -> None:
    #             with host.mount_backup_dir():
    #                 with host.sudo():
    #                     assert main_backup_file(data_file, backup).content_string.strip('\n') == s
    #                     assert main_backup_file(config_file, backup).content_string.strip('\n') == s

    #         def run_main(date: str) -> None:
    #             with host.sudo():
    #                 data_file.write(date)
    #                 config_file.write(date)
    #             with host.run_crons(date=date):
    #                 pass

    #         def backfill_main(backup: str, num: int) -> None:
    #             with host.mount_backup_dir():
    #                 with host.sudo():
    #                     out_base = main_backup_file(
    #                         data_file, backup + '.0').content_string.strip('\n')
    #                     for i in range(1, num + 1):
    #                         host.check_output(
    #                             ('cp -a %s/%s.0 '
    #                              '%s/%s.%d') % (
    #                                  backup_main_root, backup, backup_main_root, backup, i))
    #                         main_backup_file(data_file, '%s.%d' % (backup, i)).write(
    #                             '%s %d' % (out_base, i))
    #                         main_backup_file(config_file, '%s.%d' % (backup, i)).write(
    #                             '%s %d' % (out_base, i))

    #         run_main('2021-05-30')
    #         check_main('daily.0', '2021-05-30')

    #         backfill_main('daily', 6)
    #         check_main('daily.0', '2021-05-30')
    #         check_main('daily.1', '2021-05-30 1')
    #         check_main('daily.2', '2021-05-30 2')
    #         check_main('daily.3', '2021-05-30 3')
    #         check_main('daily.4', '2021-05-30 4')
    #         check_main('daily.5', '2021-05-30 5')
    #         check_main('daily.6', '2021-05-30 6')

    #         run_main('2021-05-31')
    #         check_main('daily.0', '2021-05-31')
    #         check_main('daily.1', '2021-05-30')
    #         check_main('daily.2', '2021-05-30 1')
    #         check_main('daily.3', '2021-05-30 2')
    #         check_main('daily.4', '2021-05-30 3')
    #         check_main('daily.5', '2021-05-30 4')
    #         check_main('weekly.0', '2021-05-30 5')

    #         backfill_main('weekly', 3)
    #         check_main('daily.0', '2021-05-31')
    #         check_main('daily.1', '2021-05-30')
    #         check_main('daily.2', '2021-05-30 1')
    #         check_main('daily.3', '2021-05-30 2')
    #         check_main('daily.4', '2021-05-30 3')
    #         check_main('daily.5', '2021-05-30 4')
    #         check_main('weekly.0', '2021-05-30 5')
    #         check_main('weekly.1', '2021-05-30 5 1')
    #         check_main('weekly.2', '2021-05-30 5 2')
    #         check_main('weekly.3', '2021-05-30 5 3')

    #         run_main('2021-06-01')
    #         check_main('daily.0', '2021-06-01')
    #         check_main('daily.1', '2021-05-31')
    #         check_main('daily.2', '2021-05-30')
    #         check_main('daily.3', '2021-05-30 1')
    #         check_main('daily.4', '2021-05-30 2')
    #         check_main('daily.5', '2021-05-30 3')
    #         check_main('daily.6', '2021-05-30 4')
    #         check_main('weekly.0', '2021-05-30 5')
    #         check_main('weekly.1', '2021-05-30 5 1')
    #         check_main('weekly.2', '2021-05-30 5 2')
    #         check_main('monthly.0', '2021-05-30 5 3')

    #         run_main('2021-06-02')
    #         check_main('daily.0', '2021-06-02')
    #         check_main('daily.1', '2021-06-01')
    #         check_main('daily.2', '2021-05-31')
    #         check_main('daily.3', '2021-05-30')
    #         check_main('daily.4', '2021-05-30 1')
    #         check_main('daily.5', '2021-05-30 2')
    #         check_main('daily.6', '2021-05-30 3')
    #         check_main('weekly.0', '2021-05-30 5')
    #         check_main('weekly.1', '2021-05-30 5 1')
    #         check_main('weekly.2', '2021-05-30 5 2')
    #         check_main('monthly.0', '2021-05-30 5 3')

    #         # Part 2 - git backups

    #         def write_git_config(repos: List[str]) -> None:
    #             with host.sudo():
    #                 git_config_file.write(
    #                     '\n'.join(['vagrant@%s:git/%s' % (addrs['internet'], r) for r in repos]))

    #         def run_git() -> None:
    #             email.clear()
    #             with host.run_crons():
    #                 pass

    #         def check_git_repos(repos: Set[str]) -> None:
    #             with host.mount_backup_dir():
    #                 with host.sudo():
    #                     assert set(host.file(backup_git_root).listdir()) == repos

    #         # Empty config - do nothing
    #         run_git()
    #         check_git_repos(set())
    #         email.assert_emails([], only_from=hostname)

    #         # Invalid repo - fail to clone
    #         write_git_config(['baz'])
    #         run_git()
    #         check_git_repos(set())
    #         email.assert_emails([{
    #             'from': 'notification@%s.testbed' % hostname,
    #             'to': 'fake@fake.testbed',
    #             'subject': '[%s] Cron failed' % hostname,
    #             'body_re': r'Cloning a repository failed\.\n(.*\n)*',
    #         }], only_from=hostname)

    #         # Valid repos - clone both
    #         write_git_config(['foo', 'bar'])
    #         run_git()
    #         check_git_repos({'foo', 'bar'})
    #         email.assert_emails([], only_from=hostname)

    #         # Fail to fetch
    #         try:
    #             hosts['internet'].check_output('mv git/bar git/baz')
    #             run_git()
    #             check_git_repos({'foo', 'bar'})
    #             email.assert_emails([{
    #                 'from': 'notification@%s.testbed' % hostname,
    #                 'to': 'fake@fake.testbed',
    #                 'subject': '[%s] Cron failed' % hostname,
    #                 'body_re': r'Fetching a repository failed\.\n(.*\n)*',
    #             }], only_from=hostname)
    #         finally:
    #             hosts['internet'].check_output('mv git/baz git/bar')

    #         # Valid repos - fetch both
    #         run_git()
    #         check_git_repos({'foo', 'bar'})
    #         email.assert_emails([], only_from=hostname)

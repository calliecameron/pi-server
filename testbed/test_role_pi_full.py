import os.path
import time
from typing import Dict, List, Set
from urllib.parse import urlparse
import requests
from testinfra.host import Host
from testinfra.modules.file import File
from selenium.webdriver.common.by import By
from conftest import for_host_types, host_number, Email, Lines, MockServer, WebDriver, Vagrant


class TestRolePiFull:

    # @for_host_types('pi')
    # def test_02_firewall(self, hostname: str, hosts: Dict[str, Host]) -> None:
    #     host = hosts[hostname]
    #     assert host.file('/etc/pi-server/firewall/allow-forwarding').exists

    @for_host_types('pi')
    def test_main_storage(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]

        data = host.mount_point('/mnt/data')
        assert data.exists
        assert data.filesystem == 'ext4'
        assert data.device == '/dev/sdc1'

        backup = host.mount_point('/mnt/backup')
        assert not backup.exists

        with host.mount_backup_dir():
            backup = host.mount_point('/mnt/backup')
            assert backup.exists
            assert backup.filesystem == 'ext4'
            assert backup.device == '/dev/sdc2'

    @for_host_types('pi')
    def test_main_data(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]

        assert host.file('/mnt/data/pi-server-data/config').exists
        assert host.file('/mnt/data/pi-server-data/config').user == 'root'
        assert host.file('/mnt/data/pi-server-data/config').group == 'root'

        assert host.file('/mnt/data/pi-server-data/data').exists
        assert host.file('/mnt/data/pi-server-data/data').user == 'pi-server-data'
        assert host.file('/mnt/data/pi-server-data/data').group == 'pi-server-data'

        assert host.file('/mnt/data/pi-server-data/data-no-backups').exists
        assert host.file('/mnt/data/pi-server-data/data-no-backups').user == 'pi-server-data'
        assert host.file('/mnt/data/pi-server-data/data-no-backups').group == 'pi-server-data'

        assert host.file('/mnt/data/scratch').exists
        assert host.file('/mnt/data/scratch').user == 'vagrant'
        assert host.file('/mnt/data/scratch').group == 'vagrant'

        with host.mount_backup_dir():
            assert host.file('/mnt/backup/pi-server-backup').exists
            assert host.file('/mnt/backup/pi-server-backup').user == 'root'
            assert host.file('/mnt/backup/pi-server-backup').group == 'root'

    @for_host_types('pi')
    def test_certs(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        service = host.service('pi-server-cron-certs')
        journal = host.journal()

        with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir:
            journal.clear()
            with host.run_crons():
                pass

            assert not service.is_running
            log = journal.entries('pi-server-cron-certs')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r"Wrote to '.*' for cert '.*'") == 4
            with host.sudo():
                metrics = Lines(collect_dir.file('certs.prom').content_string)
            assert metrics.count(r'cert_expiry_time{job="certs", cert=".*"} [0-9]+') == 4

    @for_host_types('pi')
    def test_syncthing(
            self,
            hostname: str,
            hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        assert host.service('pi-server-syncthing').is_enabled
        assert host.service('pi-server-syncthing').is_running
        assert host.process.filter(user='pi-server-data', comm='syncthing')

        service = host.service('pi-server-cron-syncthing-conflict-finder')
        journal = host.journal()

        # No conflicts
        with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir:
            journal.clear()
            with host.run_crons():
                pass

            assert not service.is_running
            log = journal.entries('pi-server-cron-syncthing-conflict-finder')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r"Found conflicting file.*") == 0
            assert log.count(r"Found 0 conflicting file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file('syncthing-conflicts.prom').content_string)
            assert metrics.count(r'syncthing_conflicts{job="syncthing-conflicts"} 0') == 1

        # Conflicts
        with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir, \
                host.shadow_file('/mnt/data/pi-server-data/data/foo.txt') as f1, \
                host.shadow_file('/mnt/data/pi-server-data/data/bar.sync-conflict.txt') as f2, \
                host.shadow_file(
                    '/mnt/data/pi-server-data/data-no-backups/baz.sync-conflict.txt') as f3:
            with host.sudo():
                f1.write('')
                f2.write('')
                f3.write('')
            journal.clear()
            with host.run_crons():
                pass

            assert not service.is_running
            log = journal.entries('pi-server-cron-syncthing-conflict-finder')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r"Found conflicting file.*") == 2
            assert log.count(r"Found 2 conflicting file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file('syncthing-conflicts.prom').content_string)
            assert metrics.count(r'syncthing_conflicts{job="syncthing-conflicts"} 2') == 1

    # @for_host_types('pi')
    # def test_08_openvpn_server(self, hostname: str, hosts: Dict[str, Host]) -> None:
    #     """This just installs the openvpn service, not any configs."""
    #     host = hosts[hostname]
    #     assert host.service('openvpn').is_enabled
    #     assert host.service('openvpn').is_running

    @for_host_types('pi')
    def test_backup(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email) -> None:
        host = hosts[hostname]
        backup_root = '/mnt/backup/pi-server-backup'
        backup_main_root = os.path.join(backup_root, 'main')
        backup_git_root = os.path.join(backup_root, 'git')
        data_root = '/mnt/data/pi-server-data/data'
        config_root = '/mnt/data/pi-server-data/config'
        with host.mount_backup_dir():
            assert host.file('/mnt/backup/pi-server-backup/main').exists
            assert host.file('/mnt/backup/pi-server-backup/main').user == 'root'
            assert host.file('/mnt/backup/pi-server-backup/main').group == 'root'

            assert host.file('/mnt/backup/pi-server-backup/git').exists
            assert host.file('/mnt/backup/pi-server-backup/git').user == 'pi-server-backup-git'
            assert host.file('/mnt/backup/pi-server-backup/git').group == 'pi-server-backup-git'

        def main_backup_file(path: File, backup: str) -> File:
            return host.file(
                f'{backup_main_root}/{backup}/{hostname}{path.path}')

        def clear_backups() -> None:
            with host.mount_backup_dir():
                with host.sudo():
                    host.check_output(f'rm -rf {backup_main_root}/*')
                    host.check_output(f'rm -rf {backup_git_root}/*')
                    host.check_output(f'echo > {backup_root}/last-run-date.txt')

        with host.disable_login_emails(), \
            host.shadow_file(os.path.join(data_root, 'foo.txt')) as data_file, \
            host.shadow_file(os.path.join(config_root, 'foo.txt')) as config_file, \
            host.shadow_file(
            os.path.join(
                data_root, f'{hostname}-backup-config',
                'git-backup-configuration.txt')) as git_config_file:
            clear_backups()

            # Part 1 - data backups
            # Daily backups happen every day, weekly backups happen on Mondays, and monthly backups
            # happen on the first day of the month. So we test the following dates:
            #   - 2021/05/30 (Sun): daily only
            #   - 2021/05/31 (Mon): daily and weekly
            #   - 2021/06/01 (Tue): daily and monthly
            #   - 2021/06/02 (Wed): daily only

            def check_main(backup: str, s: str) -> None:
                with host.mount_backup_dir():
                    with host.sudo():
                        assert main_backup_file(data_file, backup).content_string.strip('\n') == s
                        assert main_backup_file(config_file, backup).content_string.strip('\n') == s

            def run_main(date: str) -> None:
                with host.sudo():
                    data_file.write(date)
                    config_file.write(date)
                with host.run_crons(date=date):
                    pass

            def backfill_main(backup: str, num: int) -> None:
                with host.mount_backup_dir():
                    with host.sudo():
                        out_base = main_backup_file(
                            data_file, backup + '.0').content_string.strip('\n')
                        for i in range(1, num + 1):
                            host.check_output(
                                f'cp -a {backup_main_root}/{backup}.0 ' +
                                f'{backup_main_root}/{backup}.{i}')
                            main_backup_file(data_file, f'{backup}.{i}').write(
                                f'{out_base} {i}')
                            main_backup_file(config_file, f'{backup}.{i}').write(
                                f'{out_base} {i}')

            run_main('2021-05-30')
            check_main('daily.0', '2021-05-30')

            backfill_main('daily', 6)
            check_main('daily.0', '2021-05-30')
            check_main('daily.1', '2021-05-30 1')
            check_main('daily.2', '2021-05-30 2')
            check_main('daily.3', '2021-05-30 3')
            check_main('daily.4', '2021-05-30 4')
            check_main('daily.5', '2021-05-30 5')
            check_main('daily.6', '2021-05-30 6')

            run_main('2021-05-31')
            check_main('daily.0', '2021-05-31')
            check_main('daily.1', '2021-05-30')
            check_main('daily.2', '2021-05-30 1')
            check_main('daily.3', '2021-05-30 2')
            check_main('daily.4', '2021-05-30 3')
            check_main('daily.5', '2021-05-30 4')
            check_main('weekly.0', '2021-05-30 5')

            backfill_main('weekly', 3)
            check_main('daily.0', '2021-05-31')
            check_main('daily.1', '2021-05-30')
            check_main('daily.2', '2021-05-30 1')
            check_main('daily.3', '2021-05-30 2')
            check_main('daily.4', '2021-05-30 3')
            check_main('daily.5', '2021-05-30 4')
            check_main('weekly.0', '2021-05-30 5')
            check_main('weekly.1', '2021-05-30 5 1')
            check_main('weekly.2', '2021-05-30 5 2')
            check_main('weekly.3', '2021-05-30 5 3')

            run_main('2021-06-01')
            check_main('daily.0', '2021-06-01')
            check_main('daily.1', '2021-05-31')
            check_main('daily.2', '2021-05-30')
            check_main('daily.3', '2021-05-30 1')
            check_main('daily.4', '2021-05-30 2')
            check_main('daily.5', '2021-05-30 3')
            check_main('daily.6', '2021-05-30 4')
            check_main('weekly.0', '2021-05-30 5')
            check_main('weekly.1', '2021-05-30 5 1')
            check_main('weekly.2', '2021-05-30 5 2')
            check_main('monthly.0', '2021-05-30 5 3')

            run_main('2021-06-02')
            check_main('daily.0', '2021-06-02')
            check_main('daily.1', '2021-06-01')
            check_main('daily.2', '2021-05-31')
            check_main('daily.3', '2021-05-30')
            check_main('daily.4', '2021-05-30 1')
            check_main('daily.5', '2021-05-30 2')
            check_main('daily.6', '2021-05-30 3')
            check_main('weekly.0', '2021-05-30 5')
            check_main('weekly.1', '2021-05-30 5 1')
            check_main('weekly.2', '2021-05-30 5 2')
            check_main('monthly.0', '2021-05-30 5 3')

            # # Part 2 - git backups

            # def write_git_config(repos: List[str]) -> None:
            #     with host.sudo():
            #         git_config_file.write(
            #             '\n'.join(['vagrant@%s:git/%s' % (addrs['internet'], r) for r in repos]))

            # def run_git() -> None:
            #     email.clear()
            #     with host.run_crons():
            #         pass

            # def check_git_repos(repos: Set[str]) -> None:
            #     with host.mount_backup_dir():
            #         with host.sudo():
            #             assert set(host.file(backup_git_root).listdir()) == repos

            # # Empty config - do nothing
            # run_git()
            # check_git_repos(set())
            # email.assert_emails([], only_from=hostname)

            # # Invalid repo - fail to clone
            # write_git_config(['baz'])
            # run_git()
            # check_git_repos(set())
            # email.assert_emails([{
            #     'from': 'notification@%s.testbed' % hostname,
            #     'to': 'fake@fake.testbed',
            #     'subject': '[%s] Cron failed' % hostname,
            #     'body_re': r'Cloning a repository failed\.\n(.*\n)*',
            # }], only_from=hostname)

            # # Valid repos - clone both
            # write_git_config(['foo', 'bar'])
            # run_git()
            # check_git_repos({'foo', 'bar'})
            # email.assert_emails([], only_from=hostname)

            # # Fail to fetch
            # try:
            #     hosts['internet'].check_output('mv git/bar git/baz')
            #     run_git()
            #     check_git_repos({'foo', 'bar'})
            #     email.assert_emails([{
            #         'from': 'notification@%s.testbed' % hostname,
            #         'to': 'fake@fake.testbed',
            #         'subject': '[%s] Cron failed' % hostname,
            #         'body_re': r'Fetching a repository failed\.\n(.*\n)*',
            #     }], only_from=hostname)
            # finally:
            #     hosts['internet'].check_output('mv git/baz git/bar')

            # # Valid repos - fetch both
            # run_git()
            # check_git_repos({'foo', 'bar'})
            # email.assert_emails([], only_from=hostname)

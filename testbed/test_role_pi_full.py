import datetime
from contextlib import contextmanager
import os.path
import time
from typing import Dict, Iterator, List, Set
from urllib.parse import urlparse
from testinfra.host import Host
from testinfra.modules.file import File
from selenium.webdriver.common.by import By
from conftest import for_host_types, Email, Lines, WebDriver


class TestRolePiFull:

    @for_host_types('pi')
    def test_main_storage(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            email: Email) -> None:
        host = hosts[hostname]

        pool = host.mount_point('/mnt/data')
        assert pool.exists
        assert pool.filesystem == 'zfs'
        assert pool.device == 'data'

        data = host.mount_point('/mnt/data/pi-server-data')
        assert data.exists
        assert data.filesystem == 'zfs'
        assert data.device == 'data/pi-server-data'

        scratch = host.mount_point('/mnt/data/scratch')
        assert scratch.exists
        assert scratch.filesystem == 'zfs'
        assert scratch.device == 'data/scratch'

        @contextmanager
        def temp_zpool() -> Iterator[None]:
            with host.shadow_file('/tmp/file1') as f1, \
                    host.shadow_file('/tmp/file2') as f2:
                try:
                    with host.sudo():
                        host.check_output(f'dd if=/dev/zero of={f1.path} bs=100M count=1')
                        host.check_output(f'dd if=/dev/zero of={f2.path} bs=100M count=1')
                        host.check_output(f'zpool create test mirror {f1.path} {f2.path}')
                    yield
                finally:
                    with host.sudo():
                        host.check_output('zpool destroy test')

        @contextmanager
        def no_cron() -> Iterator[None]:
            try:
                with host.sudo():
                    host.check_output('systemctl stop cron')
                yield
            finally:
                with host.sudo():
                    host.check_output('systemctl start cron')

        def clear_prometheus() -> None:
            with host.sudo():
                host.check_output(
                    'docker-compose -f /etc/pi-server/monitoring/docker-compose.yml down')
                host.check_output('docker volume rm monitoring_prometheus-data')
                host.check_output('docker volume rm monitoring_alertmanager-data')
                host.check_output(
                    'docker-compose -f /etc/pi-server/monitoring/docker-compose.yml up -d')

        with host.disable_login_emails():

            # Test pool status
            # zed doesn't email when a single-device pool fails, so to test that it can email, we
            # have to create a temporary mirrored pool, and corrupt one of the mirrors.
            with temp_zpool():
                email.clear()
                with host.sudo():
                    host.check_output('dd if=/dev/urandom of=/tmp/file1 bs=10K count=1 seek=1')
                    host.check_output('zpool scrub test')

                time.sleep(7 * 60)

                email.assert_has_emails([
                    {
                        'from': f'notification@{hostname}.testbed',
                        'to': 'fake@fake.testbed',
                        'subject_re': (
                            fr'\[{hostname}\] ZFS device fault for pool 0x[0-9A-F]+ on {hostname}'),
                        'body_re': (
                            fr'(.*\n)* *state: UNAVAIL(.*\n)* *host: {hostname}(.*\n)* *vpath: '
                            r'/tmp/file1(.*\n)*'),
                    },
                    {
                        'from': f'notification@{hostname}.testbed',
                        'to': 'fake@fake.testbed',
                        'subject_re': fr'\[{hostname}\] ZfsPoolUnhealthy',
                        'body_re': (
                            r'Summary: A zfs pool is unhealthy\.(.*\n)*State: DEGRADED(.*\n)*'
                            r'Zpool: test(.*\n)*'),
                    },
                ], only_from=hostname)

            # Test snapshots
            with temp_zpool(), no_cron():
                email.clear()
                now = datetime.datetime.now()
                with host.sudo():
                    host.check_output(f'zfs snapshot test@{int(now.timestamp())}')

                with host.time((now + datetime.timedelta(hours=2)).time()):
                    time.sleep(5 * 60)

                    email.assert_has_emails([
                        {
                            'from': f'notification@{hostname}.testbed',
                            'to': 'fake@fake.testbed',
                            'subject_re': fr'\[{hostname}\] ZfsSnapshotTooOld',
                            'body_re': (
                                r'Summary: The latest snapshot for a zfs dataset is more than 1h '
                                r'old\.(.*\n)*Dataset: test(.*\n)*'),
                        },
                    ], only_from=hostname)

            # Test scrubbing
            try:
                with temp_zpool(), no_cron():
                    email.clear()
                    now = datetime.datetime.now()
                    with host.sudo():
                        host.check_output('zpool scrub -w test')

                    with host.time(now.time(), (now + datetime.timedelta(days=12)).date()):
                        # Big time jumps confuse prometheus, so delete its data.
                        clear_prometheus()

                        time.sleep(5 * 60)

                        email.assert_has_emails([
                            {
                                'from': f'notification@{hostname}.testbed',
                                'to': 'fake@fake.testbed',
                                'subject_re': fr'\[{hostname}\] ZfsScrubTooOld',
                                'body_re': (
                                    r'Summary: The latest scrub for a zpool is more than 10d old\.'
                                    r'(.*\n)*Zpool: test(.*\n)*'),
                            },
                        ], only_from=hostname)
            finally:
                # Big time jumps confuse prometheus, so delete its data.
                clear_prometheus()

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

    @for_host_types('pi')
    def test_syncthing(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        assert host.service('pi-server-syncthing').is_enabled
        assert host.service('pi-server-syncthing').is_running
        assert host.process.filter(user='pi-server-data', comm='syncthing')

        conflict_service_name = 'pi-server-cron-syncthing-conflict-finder'
        conflict_service = host.service(conflict_service_name)
        permission_service_name = 'pi-server-cron-syncthing-permission-fixer'
        permission_service = host.service(permission_service_name)
        journal = host.journal()

        # No conflicts, no bad permissions
        with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir:
            journal.clear()
            with host.run_crons():
                pass

            assert not conflict_service.is_running
            log = journal.entries(conflict_service_name)
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

            assert not permission_service.is_running
            log = journal.entries(permission_service_name)
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r"Fixed file.*") == 0
            assert log.count(r"Fixed 0 file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file('syncthing-permissions.prom').content_string)
            assert metrics.count(r'syncthing_permissions_fixed{job="syncthing-permissions"} 0') == 1

        # Conflicts, bad permissions
        with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir, \
                host.shadow_file('/mnt/data/pi-server-data/data/foo.txt') as f1, \
                host.shadow_file('/mnt/data/pi-server-data/data/bar.sync-conflict.txt') as f2, \
                host.shadow_file(
                    '/mnt/data/pi-server-data/data-no-backups/baz.sync-conflict.txt') as f3:
            with host.sudo():
                f1.write('')
                host.check_output(f'chmod u=rw,go=rwx {f1.path}')
                host.check_output(f'chown pi-server-data:pi-server-data {f1.path}')
                assert host.file(f1.path).mode == 0o677
                f2.write('')
                host.check_output(f'chmod u=rw,go= {f2.path}')
                host.check_output(f'chown pi-server-data:pi-server-data {f2.path}')
                assert host.file(f2.path).mode == 0o600
                f3.write('')
                host.check_output(f'chmod u=rwx,go= {f3.path}')
                host.check_output(f'chown pi-server-data:pi-server-data {f3.path}')
                assert host.file(f3.path).mode == 0o700
            journal.clear()
            with host.run_crons():
                pass

            assert not conflict_service.is_running
            log = journal.entries(conflict_service_name)
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

            assert not permission_service.is_running
            log = journal.entries(permission_service_name)
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r"Fixed file.*") == 1
            assert log.count(r"Fixed 1 file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file('syncthing-permissions.prom').content_string)
            assert metrics.count(r'syncthing_permissions_fixed{job="syncthing-permissions"} 1') == 1

            with host.sudo():
                assert host.file(f1.path).mode == 0o600

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value='Control panel')
                assert urlparse(link.get_attribute('href')).hostname == this_addr
                driver.click(link)
                time.sleep(5)
                assert driver.title == f'{hostname} | Syncthing'

        test(addrs[hostname])
        test(hostname + '.local')

    @for_host_types('pi')
    def test_minidlna(
            self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        assert host.service('minidlna').is_enabled
        assert host.service('minidlna').is_running
        assert host.process.filter(user='pi-server-data', comm='minidlnad')

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value='Minidlna status')
                assert urlparse(link.get_attribute('href')).hostname == this_addr
                driver.click(link)
                assert driver.title.startswith('MiniDLNA')

        test(addrs[hostname])
        test(hostname + '.local')

    @for_host_types('pi')
    def test_pihole(self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        host = hosts[hostname]

        # Good domain
        assert not Lines(host.check_output('nslookup google.com')).contains(r'Address: 0\.0\.0\.0')
        assert not Lines(host.check_output('nslookup google.com localhost')
                         ).contains(r'Address: 0\.0\.0\.0')

        # Ad-serving domain
        assert not Lines(host.check_output('nslookup ads.google.com')
                         ).contains(r'Address: 0\.0\.0\.0')
        assert Lines(host.check_output('nslookup ads.google.com localhost')
                     ).contains(r'Address: 0\.0\.0\.0')

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get('http://' + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value='Pi-hole')
                assert urlparse(link.get_attribute('href')).hostname == this_addr
                driver.click(link)
                assert driver.title == f'Pi-hole - {hostname}'

        test(addrs[hostname])
        test(hostname + '.local')

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
            assert log.count(r"Wrote to '.*' for cert '.*'") == 5
            with host.sudo():
                metrics = Lines(collect_dir.file('certs.prom').content_string)
            assert metrics.count(r'cert_expiry_time{job="certs", cert=".*"} [0-9]+') == 5

    @for_host_types('pi')
    def test_backup(
            self,
            hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        journal = host.journal()
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
            assert host.file('/mnt/backup/pi-server-backup/git').user == 'pi-server-data'
            assert host.file('/mnt/backup/pi-server-backup/git').group == 'pi-server-data'

        def main_backup_file(path: File, backup: str) -> File:
            return host.file(
                f'{backup_main_root}/{backup}/{hostname}{path.path}')

        def clear_backups() -> None:
            with host.mount_backup_dir():
                with host.sudo():
                    host.check_output(f'rm -rf {backup_main_root}/*')
                    host.check_output(f'rm -rf {backup_git_root}/*')
                    host.check_output(f'echo > {backup_root}/last-run-date.txt')

        with host.shadow_file(os.path.join(data_root, 'foo.txt')) as data_file, \
            host.shadow_file(os.path.join(config_root, 'foo.txt')) as config_file, \
            host.shadow_dir(
                os.path.join(
                    data_root, f'{hostname}-backup-config')) as git_config_dir:
            git_config_file = git_config_dir.file('git-backup-configuration.txt')
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
                with host.run_crons(date=datetime.date.fromisoformat(date)):
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

            # Part 2 - git backups

            def write_git_config(repos: List[str]) -> None:
                with host.sudo():
                    git_config_file.write(
                        '\n'.join([f'vagrant@{addrs["internet"]}:git/{r}' for r in repos]))
                    host.check_output(
                        f"chown pi-server-data:pi-server-data '{git_config_file.path}'")
                    host.check_output(
                        f"chmod u=rw,go= '{git_config_file.path}'")

            def run_git() -> None:
                journal.clear()
                with host.run_crons():
                    pass

            def check_git_repos(repos: Set[str]) -> None:
                with host.mount_backup_dir():
                    with host.sudo():
                        assert set(host.file(backup_git_root).listdir()) == repos

            # Empty config - do nothing
            run_git()
            check_git_repos(set())
            log = journal.entries('pi-server-cron-backup-git')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 1
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Checking .* repo\(s\)') == 0
            assert log.count(r'.*config file does not exist') == 1
            assert log.count(r'Updated.*') == 0
            assert log.count(r'Cloned.*') == 0
            assert log.count(r'.*cloning.*failed') == 0
            assert log.count(r'.*fetching.*failed') == 0

            # Invalid repo - fail to clone
            write_git_config(['baz'])
            run_git()
            check_git_repos(set())
            log = journal.entries('pi-server-cron-backup-git')
            assert log.count(r'.*ERROR.*') == 1
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 2
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 0
            assert log.count(r'Checking 1 repo\(s\)') == 1
            assert log.count(r'.*config file does not exist') == 0
            assert log.count(r'Updated.*') == 0
            assert log.count(r'Cloned.*') == 0
            assert log.count(r'.*cloning.*failed') == 1
            assert log.count(r'.*fetching.*failed') == 0

            # Valid repos - clone both
            write_git_config(['foo', 'bar'])
            run_git()
            check_git_repos({'foo', 'bar'})
            log = journal.entries('pi-server-cron-backup-git')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Checking 2 repo\(s\)') == 1
            assert log.count(r'.*config file does not exist') == 0
            assert log.count(r'Updated.*') == 0
            assert log.count(r'Cloned.*') == 2
            assert log.count(r'.*cloning.*failed') == 0
            assert log.count(r'.*fetching.*failed') == 0

            # Fail to fetch
            try:
                hosts['internet'].check_output('mv git/bar git/baz')
                run_git()
                check_git_repos({'foo', 'bar'})
                log = journal.entries('pi-server-cron-backup-git')
                assert log.count(r'.*ERROR.*') == 1
                assert log.count(r'.*WARNING.*') == 0
                assert log.count(r'.*FAILURE.*') == 2
                assert log.count(r'.*KILLED.*') == 0
                assert log.count(r'.*SUCCESS.*') == 0
                assert log.count(r'Checking 2 repo\(s\)') == 1
                assert log.count(r'.*config file does not exist') == 0
                assert log.count(r'Updated.*') == 1
                assert log.count(r'Cloned.*') == 0
                assert log.count(r'.*cloning.*failed') == 0
                assert log.count(r'.*fetching.*failed') == 1
            finally:
                hosts['internet'].check_output('mv git/baz git/bar')

            # Valid repos - fetch both
            run_git()
            check_git_repos({'foo', 'bar'})
            log = journal.entries('pi-server-cron-backup-git')
            assert log.count(r'.*ERROR.*') == 0
            assert log.count(r'.*WARNING.*') == 0
            assert log.count(r'.*FAILURE.*') == 0
            assert log.count(r'.*KILLED.*') == 0
            assert log.count(r'.*SUCCESS.*') == 1
            assert log.count(r'Checking 2 repo\(s\)') == 1
            assert log.count(r'.*config file does not exist') == 0
            assert log.count(r'Updated.*') == 2
            assert log.count(r'Cloned.*') == 0
            assert log.count(r'.*cloning.*failed') == 0
            assert log.count(r'.*fetching.*failed') == 0

    @for_host_types('pi')
    def test_openvpn_server(self, hostname: str, hosts: Dict[str, Host]) -> None:
        """This just installs the openvpn service, not any configs."""
        host = hosts[hostname]
        assert host.service('openvpn').is_enabled
        assert host.service('openvpn').is_running

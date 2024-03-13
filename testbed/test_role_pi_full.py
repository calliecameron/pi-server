import datetime
import json
import os.path
import time
from collections.abc import Iterator, Mapping, Sequence, Set
from contextlib import contextmanager
from urllib.parse import urlparse

from conftest import for_host_types
from helpers import Email, Lines, WebDriver
from selenium.webdriver.common.by import By
from testinfra.host import Host

# ruff: noqa: PLR2004, DTZ005


class TestRolePiFull:
    @for_host_types("pi")
    def test_main_storage(self, hostname: str, hosts: Mapping[str, Host], email: Email) -> None:
        host = hosts[hostname]

        pool = host.mount_point("/mnt/data")
        assert pool.exists
        assert pool.filesystem == "zfs"
        assert pool.device == "data"

        data = host.mount_point("/mnt/data/pi-server-data")
        assert data.exists
        assert data.filesystem == "zfs"
        assert data.device == "data/pi-server-data"

        scratch = host.mount_point("/mnt/data/scratch")
        assert scratch.exists
        assert scratch.filesystem == "zfs"
        assert scratch.device == "data/scratch"

        @contextmanager
        def temp_zpool() -> Iterator[None]:
            with host.shadow_file("/tmp/file1") as f1, host.shadow_file("/tmp/file2") as f2:
                try:
                    with host.sudo():
                        host.check_output(f"dd if=/dev/zero of={f1.path} bs=100M count=1")
                        host.check_output(f"dd if=/dev/zero of={f2.path} bs=100M count=1")
                        host.check_output(f"zpool create test mirror {f1.path} {f2.path}")
                    yield
                finally:
                    with host.sudo():
                        host.check_output("zpool destroy test")

        @contextmanager
        def no_cron() -> Iterator[None]:
            try:
                with host.sudo():
                    host.check_output("systemctl stop cron")
                yield
            finally:
                with host.sudo():
                    host.check_output("systemctl start cron")

        def clear_prometheus() -> None:
            with host.sudo():
                host.check_output(
                    "docker-compose -f /etc/pi-server/monitoring/docker-compose.yml down",
                )
                host.check_output("docker volume rm monitoring_prometheus-data")
                host.check_output("docker volume rm monitoring_alertmanager-data")
                host.check_output(
                    "docker-compose -f /etc/pi-server/monitoring/docker-compose.yml up -d",
                )

        with host.disable_login_emails():
            # Test pool status
            # zed doesn't email when a single-device pool fails, so to test that it can email, we
            # have to create a temporary mirrored pool, and corrupt one of the mirrors.
            with temp_zpool():
                email.clear()
                with host.sudo():
                    host.check_output("dd if=/dev/urandom of=/tmp/file1 bs=10K count=1 seek=1")
                    host.check_output("zpool scrub test")

                time.sleep(7 * 60)

                email.assert_has_emails(
                    [
                        {
                            "from": f"notification@{hostname}.testbed",
                            "to": "fake@fake.testbed",
                            "subject_re": (
                                rf"\[{hostname}\] ZFS device fault for pool 0x[0-9A-F]+ on "
                                rf"{hostname}"
                            ),
                            "body_re": (
                                rf"(.*\n)* *state: UNAVAIL(.*\n)* *host: {hostname}(.*\n)* *vpath: "
                                r"/tmp/file1(.*\n)*"
                            ),
                        },
                        {
                            "from": f"notification@{hostname}.testbed",
                            "to": "fake@fake.testbed",
                            "subject_re": rf"\[{hostname}\] ZfsPoolUnhealthy",
                            "body_re": (
                                r"Summary: A zfs pool is unhealthy\.(.*\n)*State: DEGRADED(.*\n)*"
                                r"Zpool: test(.*\n)*"
                            ),
                        },
                    ],
                    only_from=hostname,
                )

            # Test snapshots
            with temp_zpool(), no_cron():
                email.clear()
                now = datetime.datetime.now()
                with host.sudo():
                    host.check_output(f"zfs snapshot test@{int(now.timestamp())}")

                with host.time((now + datetime.timedelta(hours=2)).time()):
                    time.sleep(5 * 60)

                    email.assert_has_emails(
                        [
                            {
                                "from": f"notification@{hostname}.testbed",
                                "to": "fake@fake.testbed",
                                "subject_re": rf"\[{hostname}\] ZfsSnapshotTooOld",
                                "body_re": (
                                    r"Summary: The latest snapshot for a zfs dataset is more than "
                                    r"1h old\.(.*\n)*Dataset: test(.*\n)*"
                                ),
                            },
                        ],
                        only_from=hostname,
                    )

            # Test scrubbing
            try:
                with temp_zpool(), no_cron():
                    email.clear()
                    now = datetime.datetime.now()
                    with host.sudo():
                        host.check_output("zpool scrub -w test")

                    with host.time(now.time(), (now + datetime.timedelta(days=12)).date()):
                        # Big time jumps confuse prometheus, so delete its data.
                        clear_prometheus()

                        time.sleep(5 * 60)

                        email.assert_has_emails(
                            [
                                {
                                    "from": f"notification@{hostname}.testbed",
                                    "to": "fake@fake.testbed",
                                    "subject_re": rf"\[{hostname}\] ZfsScrubTooOld",
                                    "body_re": (
                                        r"Summary: The latest scrub for a zpool is more than 10d "
                                        r"old\.(.*\n)*Zpool: test(.*\n)*"
                                    ),
                                },
                            ],
                            only_from=hostname,
                        )
            finally:
                # Big time jumps confuse prometheus, so delete its data.
                clear_prometheus()

    @for_host_types("pi")
    def test_main_data(self, hostname: str, hosts: Mapping[str, Host]) -> None:
        host = hosts[hostname]

        assert host.file("/mnt/data/pi-server-data/config").exists
        assert host.file("/mnt/data/pi-server-data/config").user == "root"
        assert host.file("/mnt/data/pi-server-data/config").group == "root"

        assert host.file("/mnt/data/pi-server-data/data").exists
        assert host.file("/mnt/data/pi-server-data/data").user == "pi-server-data"
        assert host.file("/mnt/data/pi-server-data/data").group == "pi-server-data"

        assert host.file("/mnt/data/pi-server-data/data-no-backups").exists
        assert host.file("/mnt/data/pi-server-data/data-no-backups").user == "pi-server-data"
        assert host.file("/mnt/data/pi-server-data/data-no-backups").group == "pi-server-data"

        assert host.file("/mnt/data/scratch").exists
        assert host.file("/mnt/data/scratch").user == "vagrant"
        assert host.file("/mnt/data/scratch").group == "vagrant"

    @for_host_types("pi")
    def test_syncthing(
        self,
        hostname: str,
        hosts: Mapping[str, Host],
        addrs: Mapping[str, str],
    ) -> None:
        host = hosts[hostname]
        assert host.service("pi-server-syncthing").is_enabled
        assert host.service("pi-server-syncthing").is_running
        assert host.process.filter(user="pi-server-data", comm="syncthing")

        conflict_service_name = "pi-server-cron-syncthing-conflict-finder"
        conflict_service = host.service(conflict_service_name)
        permission_service_name = "pi-server-cron-syncthing-permission-fixer"
        permission_service = host.service(permission_service_name)
        journal = host.journal()

        # No conflicts, no bad permissions
        with host.shadow_dir("/var/pi-server/monitoring/collect") as collect_dir:
            journal.clear()
            with host.run_crons():
                pass

            assert not conflict_service.is_running
            log = journal.entries(conflict_service_name)
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Found conflicting file.*") == 0
            assert log.count(r"Found 0 conflicting file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file("syncthing-conflicts.prom").content_string)
            assert metrics.count(r'syncthing_conflicts{job="syncthing-conflicts"} 0') == 1

            assert not permission_service.is_running
            log = journal.entries(permission_service_name)
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Fixed file.*") == 0
            assert log.count(r"Fixed 0 file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file("syncthing-permissions.prom").content_string)
            assert metrics.count(r'syncthing_permissions_fixed{job="syncthing-permissions"} 0') == 1

        # Conflicts, bad permissions
        with (
            host.shadow_dir("/var/pi-server/monitoring/collect") as collect_dir,
            host.shadow_file("/mnt/data/pi-server-data/data/foo.txt") as f1,
            host.shadow_file("/mnt/data/pi-server-data/data/bar.sync-conflict.txt") as f2,
            host.shadow_file(
                "/mnt/data/pi-server-data/data-no-backups/baz.sync-conflict.txt",
            ) as f3,
        ):
            with host.sudo():
                f1.write("")
                host.check_output(f"chmod u=rw,go=rwx {f1.path}")
                host.check_output(f"chown pi-server-data:pi-server-data {f1.path}")
                assert host.file(f1.path).mode == 0o677
                f2.write("")
                host.check_output(f"chmod u=rw,go= {f2.path}")
                host.check_output(f"chown pi-server-data:pi-server-data {f2.path}")
                assert host.file(f2.path).mode == 0o600
                f3.write("")
                host.check_output(f"chmod u=rwx,go= {f3.path}")
                host.check_output(f"chown pi-server-data:pi-server-data {f3.path}")
                assert host.file(f3.path).mode == 0o700
            journal.clear()
            with host.run_crons():
                pass

            assert not conflict_service.is_running
            log = journal.entries(conflict_service_name)
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Found conflicting file.*") == 2
            assert log.count(r"Found 2 conflicting file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file("syncthing-conflicts.prom").content_string)
            assert metrics.count(r'syncthing_conflicts{job="syncthing-conflicts"} 2') == 1

            assert not permission_service.is_running
            log = journal.entries(permission_service_name)
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Fixed file.*") == 1
            assert log.count(r"Fixed 1 file\(s\)") == 1
            with host.sudo():
                metrics = Lines(collect_dir.file("syncthing-permissions.prom").content_string)
            assert metrics.count(r'syncthing_permissions_fixed{job="syncthing-permissions"} 1') == 1

            with host.sudo():
                assert host.file(f1.path).mode == 0o600

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get("http://" + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value="Control panel")
                assert urlparse(link.get_attribute("href")).hostname == this_addr
                driver.click(link)
                time.sleep(5)
                assert driver.title == f"{hostname} | Syncthing"

        test(addrs[hostname])
        test(hostname + ".local")

    @for_host_types("pi")
    def test_minidlna(
        self,
        hostname: str,
        addrs: Mapping[str, str],
    ) -> None:
        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get("http://" + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value="Minidlna status")
                assert urlparse(link.get_attribute("href")).hostname == this_addr
                driver.click(link)
                assert driver.title.startswith("MiniDLNA")

        test(addrs[hostname])
        # No longer works since https://security.snyk.io/vuln/SNYK-UNMANAGED-MINIDLNA-2419090
        # test(hostname + ".local") # noqa: ERA001

    @for_host_types("pi")
    def test_photoprism(
        self,
        hostname: str,
        addrs: Mapping[str, str],
    ) -> None:
        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get("http://" + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value="PhotoPrism")
                assert urlparse(link.get_attribute("href")).hostname == this_addr
                driver.click(link)
                assert driver.title.startswith("PhotoPrism")

        test(addrs[hostname])
        test(hostname + ".local")

    @for_host_types("pi")
    def test_pihole(
        self,
        hostname: str,
        hosts: Mapping[str, Host],
        addrs: Mapping[str, str],
    ) -> None:
        host = hosts[hostname]

        # Good domain
        assert not Lines(host.check_output("nslookup google.com")).contains(r"Address: 0\.0\.0\.0")
        assert not Lines(host.check_output("nslookup google.com localhost")).contains(
            r"Address: 0\.0\.0\.0",
        )

        # Ad-serving domain
        # Note that this will fail if pihole is enabled on your network -
        # disable it before running the test.
        assert not Lines(host.check_output("nslookup ads.google.com")).contains(
            r"Address: 0\.0\.0\.0",
        )
        assert Lines(host.check_output("nslookup ads.google.com localhost")).contains(
            r"Address: 0\.0\.0\.0",
        )

        def test(this_addr: str) -> None:
            with WebDriver() as driver:
                driver.get("http://" + this_addr)
                link = driver.find_element(by=By.LINK_TEXT, value="Pi-hole")
                assert urlparse(link.get_attribute("href")).hostname == this_addr
                driver.click(link)
                assert driver.title == f"Pi-hole - {hostname}"

        test(addrs[hostname])
        test(hostname + ".local")

    @for_host_types("pi")
    def test_certs(self, hostname: str, hosts: Mapping[str, Host]) -> None:
        host = hosts[hostname]
        service = host.service("pi-server-cron-certs")
        journal = host.journal()

        with host.shadow_dir("/var/pi-server/monitoring/collect") as collect_dir:
            journal.clear()
            with host.run_crons():
                pass

            assert not service.is_running
            log = journal.entries("pi-server-cron-certs")
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Wrote to '.*' for cert '.*'") == 5
            with host.sudo():
                metrics = Lines(collect_dir.file("certs.prom").content_string)
            assert metrics.count(r'cert_expiry_time{job="certs", cert=".*"} [0-9]+') == 5

    @for_host_types("pi")
    def test_backup_git(
        self,
        hostname: str,
        hosts: Mapping[str, Host],
        addrs: Mapping[str, str],
    ) -> None:
        host = hosts[hostname]
        journal = host.journal()
        backup_git_root = "/mnt/data/pi-server-data/git-backup"
        data_root = "/mnt/data/pi-server-data/data"

        assert host.file(backup_git_root).exists
        assert host.file(backup_git_root).user == "pi-server-data"
        assert host.file(backup_git_root).group == "pi-server-data"

        with host.shadow_dir(
            os.path.join(data_root, f"{hostname}-backup-config"),
        ) as git_config_dir:
            git_config_file = git_config_dir.file("git-backup-configuration.txt")

            with host.sudo():
                host.check_output(f"rm -rf {backup_git_root}/*")

            def write_git_config(repos: Sequence[str]) -> None:
                with host.sudo():
                    git_config_file.write(
                        "\n".join([f'vagrant@{addrs["internet"]}:git/{r}' for r in repos]),
                    )
                    host.check_output(
                        f"chown pi-server-data:pi-server-data '{git_config_file.path}'",
                    )
                    host.check_output(f"chmod u=rw,go= '{git_config_file.path}'")

            def run_git() -> None:
                journal.clear()
                with host.run_crons():
                    pass

            def check_git_repos(repos: Set[str]) -> None:
                with host.sudo():
                    assert set(host.file(backup_git_root).listdir()) == repos

            # Empty config - do nothing
            run_git()
            check_git_repos(set())
            log = journal.entries("pi-server-cron-backup-git")
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 1
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Checking .* repo\(s\)") == 0
            assert log.count(r".*config file does not exist") == 1
            assert log.count(r"Updated.*") == 0
            assert log.count(r"Cloned.*") == 0
            assert log.count(r".*cloning.*failed") == 0
            assert log.count(r".*fetching.*failed") == 0

            # Invalid repo - fail to clone
            write_git_config(["baz"])
            run_git()
            check_git_repos(set())
            log = journal.entries("pi-server-cron-backup-git")
            assert log.count(r".*ERROR.*") == 1
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 2
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 0
            assert log.count(r"Checking 1 repo\(s\)") == 1
            assert log.count(r".*config file does not exist") == 0
            assert log.count(r"Updated.*") == 0
            assert log.count(r"Cloned.*") == 0
            assert log.count(r".*cloning.*failed") == 1
            assert log.count(r".*fetching.*failed") == 0

            # Valid repos - clone both
            write_git_config(["foo", "bar"])
            run_git()
            check_git_repos({"foo", "bar"})
            log = journal.entries("pi-server-cron-backup-git")
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Checking 2 repo\(s\)") == 1
            assert log.count(r".*config file does not exist") == 0
            assert log.count(r"Updated.*") == 0
            assert log.count(r"Cloned.*") == 2
            assert log.count(r".*cloning.*failed") == 0
            assert log.count(r".*fetching.*failed") == 0

            # Fail to fetch
            try:
                hosts["internet"].check_output("mv git/bar git/baz")
                run_git()
                check_git_repos({"foo", "bar"})
                log = journal.entries("pi-server-cron-backup-git")
                assert log.count(r".*ERROR.*") == 1
                assert log.count(r".*WARNING.*") == 0
                assert log.count(r".*FAILURE.*") == 2
                assert log.count(r".*KILLED.*") == 0
                assert log.count(r".*SUCCESS.*") == 0
                assert log.count(r"Checking 2 repo\(s\)") == 1
                assert log.count(r".*config file does not exist") == 0
                assert log.count(r"Updated.*") == 1
                assert log.count(r"Cloned.*") == 0
                assert log.count(r".*cloning.*failed") == 0
                assert log.count(r".*fetching.*failed") == 1
            finally:
                hosts["internet"].check_output("mv git/baz git/bar")

            # Valid repos - fetch both
            run_git()
            check_git_repos({"foo", "bar"})
            log = journal.entries("pi-server-cron-backup-git")
            assert log.count(r".*ERROR.*") == 0
            assert log.count(r".*WARNING.*") == 0
            assert log.count(r".*FAILURE.*") == 0
            assert log.count(r".*KILLED.*") == 0
            assert log.count(r".*SUCCESS.*") == 1
            assert log.count(r"Checking 2 repo\(s\)") == 1
            assert log.count(r".*config file does not exist") == 0
            assert log.count(r"Updated.*") == 2
            assert log.count(r"Cloned.*") == 0
            assert log.count(r".*cloning.*failed") == 0
            assert log.count(r".*fetching.*failed") == 0

    @for_host_types("pi")
    def test_backup_main(self, hostname: str, hosts: Mapping[str, Host]) -> None:
        host = hosts[hostname]
        journal = host.journal()

        try:
            repo = "/tmp/backup-test"
            with host.sudo():
                host.check_output(f"mkdir {repo}")

            with (
                host.shadow_dir("/mnt/data/pi-server-data/config/restic/cache"),
                host.shadow_file("/etc/pi-server/backup/restic.conf") as conf,
                host.shadow_file("/mnt/data/pi-server-data/data/foo.txt") as data_file,
            ):
                with host.sudo():
                    host.check_output(f"RESTIC_PASSWORD=foobar restic init -r {repo}")
                    host.check_output(f"chown -R pi-server-data:pi-server-data {repo}")
                    conf.write(
                        "\n".join(
                            [
                                f"export RESTIC_REPOSITORY='{repo}'",
                                "export RESTIC_PASSWORD='foobar'",
                                "export RESTIC_HOSTNAME='main'",
                                "export B2_ACCOUNT_ID=''",
                                "export B2_ACCOUNT_KEY=''",
                            ],
                        ),
                    )
                    host.check_output(f"chown pi-server-data:pi-server-data {data_file.path}")

                def check_journal() -> None:
                    log = journal.entries("pi-server-cron-backup-main")
                    assert log.count(r".*ERROR.*") == 0
                    assert log.count(r".*WARNING.*") == 0
                    assert log.count(r".*FAILURE.*") == 0
                    assert log.count(r".*KILLED.*") == 0
                    assert log.count(r".*SUCCESS.*") == 1
                    assert log.count(r"Backup completed") == 1
                    assert log.count(r"Forget completed") == 1
                    assert log.count(r"Prune completed") == 1
                    assert log.count(r"Check completed") == 1

                def write_data(date: datetime.date) -> None:
                    with host.sudo():
                        data_file.write(date.isoformat())

                def run_cron(date: datetime.date) -> None:
                    write_data(date)
                    journal.clear()
                    with host.run_crons(date=date):
                        pass
                    check_journal()

                def all_snapshots() -> dict[str, str]:
                    with host.sudo():
                        raw = json.loads(
                            host.check_output(
                                f"RESTIC_PASSWORD=foobar restic snapshots -r {repo} --json",
                            ),
                        )
                    out = {}
                    for snapshot in raw:
                        date = snapshot["time"][:10]
                        if date in out:
                            raise ValueError(f"Multiple snapshots for {date}: {raw}")
                        out[date] = snapshot["short_id"]
                    return out

                def check_date(date: str, snapshot: str) -> None:
                    restore = "/tmp/restore-test"
                    try:
                        with host.sudo():
                            host.check_output(f"mkdir {restore}")
                            host.check_output(
                                f"RESTIC_PASSWORD=foobar restic restore -r {repo} "
                                f"-t {restore} {snapshot}",
                            )
                            assert (
                                host.file(f"{restore}/backup/foo.txt").content_string.strip()
                                == date
                            )
                    finally:
                        with host.sudo():
                            host.check_output(f"rm -rf {restore}")

                def check(dates: Sequence[str]) -> None:
                    snapshots = all_snapshots()
                    assert set(dates) == set(snapshots.keys())
                    for date in dates:
                        check_date(date, snapshots[date])

                # When running daily, weekly keeps Sundays; monthly keeps the last day of the month;
                # both will keep the latest snapshot in an unfinished period
                # So after running from 2021/05/20 (Thu) - 2021/06/19 (Sat), we'd expect to see:
                #   - 2021/06/19 (Sat, daily, weekly, monthly, yearly)
                #   - 2021/06/18 (Fri, daily)
                #   - 2021/06/17 (Thu, daily)
                #   - 2021/06/16 (Wed, daily)
                #   - 2021/06/15 (Tue, daily)
                #   - 2021/06/14 (Mon, daily)
                #   - 2021/06/13 (Sun, daily and weekly)
                #   - 2021/06/06 (Sun, weekly)
                #   - 2021/05/31 (Mon, monthly)
                #   - 2021/05/30 (Sun, weekly)

                run_cron(datetime.date(year=2021, month=5, day=20))
                check(["2021-05-20"])

                # Running with cron is slow, so we run the rest manually
                t = datetime.time(hour=9)
                start = datetime.date(year=2021, month=5, day=21)
                try:
                    with host.sudo():
                        host.check_output("systemctl stop pi-server-syncthing")
                    with host.time(t, start) as time_control:

                        def run_manually(date: datetime.date) -> None:
                            write_data(date)
                            journal.clear()
                            time_control.set_time(t, date)
                            with host.sudo():
                                host.check_output(
                                    "systemctl start --wait pi-server-cron-backup-main",
                                )
                            check_journal()

                        for i in range(30):
                            run_manually(start + datetime.timedelta(days=i))
                finally:
                    with host.sudo():
                        host.check_output("systemctl start pi-server-syncthing")

                check(
                    [
                        "2021-05-30",
                        "2021-05-31",
                        "2021-06-06",
                        "2021-06-13",
                        "2021-06-14",
                        "2021-06-15",
                        "2021-06-16",
                        "2021-06-17",
                        "2021-06-18",
                        "2021-06-19",
                    ],
                )

        finally:
            with host.sudo():
                host.check_output(f"rm -rf {repo}")

    @for_host_types("pi")
    def test_openvpn_server(self, hostname: str, hosts: Mapping[str, Host]) -> None:
        """This just installs the openvpn service, not any configs."""
        host = hosts[hostname]
        assert host.service("openvpn").is_enabled
        assert host.service("openvpn").is_running

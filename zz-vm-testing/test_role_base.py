import time
from typing import Dict
from testinfra.host import Host
from conftest import Email, Lines, for_host_types


class TestRoleBase:
    @for_host_types('pi', 'ubuntu')
    def test_hostname(self, hostname: str, hosts: Dict[str, Host]) -> None:
        assert hosts[hostname].check_output('hostname') == hostname

    @for_host_types('pi', 'ubuntu')
    def test_localisation(self, hostname: str, hosts: Dict[str, Host]) -> None:
        lines = Lines(hosts[hostname].check_output('timedatectl status'), hostname)
        assert lines.contains(r' *Time zone: Europe/Zurich.*')

        lines = Lines(hosts[hostname].check_output('localectl status'), hostname)
        assert lines.contains(r' *System Locale: LANG=en_GB.UTF-8')

    @for_host_types('pi', 'ubuntu')
    def test_packages(self, hostname: str, hosts: Dict[str, Host]) -> None:
        # We pick one of the packages that the script installs, that isn't installed by default.
        assert hosts[hostname].package('etckeeper').is_installed

    @for_host_types('pi', 'ubuntu')
    def test_cleanup_users(self, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        # We pick the most important user - root - and a few that are changed
        with host.sudo():
            assert host.user('root').password == '!*'
            assert host.user('systemd-timesync').shell == '/usr/sbin/nologin'
            assert host.user('systemd-timesync').password == '*'
            assert host.user('messagebus').shell == '/usr/sbin/nologin'
            assert host.user('messagebus').password == '*'

    @for_host_types('pi', 'ubuntu')
    def test_email(self, email: Email, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        client_ip = host.client_ip()

        email.clear()

        # SSH login emails are on by default, so we expect one email for logging in, and one for
        # the command we actually ran.
        host.check_output('/etc/pi-server/email/send-email foo bar')
        time.sleep(10)
        email.assert_emails([
            {
                'from': f'notification@{hostname}.testbed',
                'to': 'fake@fake.testbed',
                'subject': f'[{hostname}] SSH login: vagrant from {client_ip}',
                'body_re': (r'(.*\n)*PAM_USER=vagrant\n(.*\n)*PAM_RHOST=%s\n(.*\n)*' %
                            client_ip.replace('.', r'\.')),
            },
            {
                'from': f'notification@{hostname}.testbed',
                'to': 'fake@fake.testbed',
                'subject': f'[{hostname}] foo',
                'body_re': r'bar\n\n',
            },
        ], only_from=hostname)

        # Disable SSH login emails from our address, and we should only get one email.
        with host.disable_login_emails():
            email.clear()

            host.check_output('/etc/pi-server/email/send-email foo bar')
            time.sleep(10)
            email.assert_emails([
                {
                    'from': f'notification@{hostname}.testbed',
                    'to': 'fake@fake.testbed',
                    'subject': f'[{hostname}] foo',
                    'body_re': r'bar\n\n',
                },
            ], only_from=hostname)

    # SSH is partially tested by the fact we can still log in at all, and partially
    # by the email-at-login behaviour.

    # Firewall is tested by the port scan in test_base.py.

    @for_host_types('pi', 'ubuntu')
    def test_docker(self, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        assert host.service('docker').is_enabled
        assert host.service('docker').is_running
        assert host.exists('docker-compose')

    @for_host_types('pi', 'ubuntu')
    def test_monitoring(self, email: Email, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        textfile_alert = """
groups:
  - name: "test alerts"
    rules:
      - alert: TestAlert
        expr: pi_server_test_test{job="test"} > 0
        annotations:
          summary: "Test alert."
        """
        jobmissing_alerts = """
groups:
  - name: "test alerts"
    rules:
      - alert: TestDockerJobMissing
        expr: absent(container_last_seen{job="cadvisor", name="monitoring_grafana_1"})
        annotations:
          summary: "Grafana missing"
      - alert: TestSystemdJobMissing
        expr: absent(container_last_seen{job="cadvisor", id="/system.slice/cron.service"})
        annotations:
          summary: "Cron missing"
        """
        with host.disable_login_emails():
            # Custom alert through the textfile exporter
            # textfile -> node exporter -> scrape -> prometheus -> alertmanager -> webhook
            email.clear()
            try:
                with host.shadow_file('/etc/pi-server/monitoring/rules.d/test.yml') as rules, \
                        host.shadow_file('/var/pi-server/monitoring/collect/test.prom') as data:
                    with host.sudo():
                        rules.write(textfile_alert)
                        host.check_output('chmod a=r /etc/pi-server/monitoring/rules.d/test.yml')
                        host.check_output('pkill -HUP prometheus')  # reload rules
                        data.write('pi_server_test_test{job="test"} 1')
                    time.sleep(90)  # prometheus scrapes every minute
                    email.assert_has_emails([
                        {
                            'from': f'notification@{hostname}.testbed',
                            'to': 'fake@fake.testbed',
                            'subject': f'[{hostname}] TestAlert',
                            'body_re': (fr'Summary: Test alert.(.*\n)+Instance: {hostname}(.*\n)+'
                                        r'Job: test(.*\n)+Alert 1 of 1:(.*\n)+'),
                        }
                    ], only_from=hostname)
            finally:
                with host.sudo():
                    host.check_output('pkill -HUP prometheus')  # reload rules

            # Disk space full alert through the node exporter
            # node exporter -> scrape -> prometheus -> alertmanager -> webhook
            email.clear()
            try:
                host.make_bigfile('bigfile', '/')
                time.sleep(300)  # alert has a 2m trigger duration, plus scrape delay
                email.assert_has_emails([
                    {
                        'from': f'notification@{hostname}.testbed',
                        'to': 'fake@fake.testbed',
                        'subject': f'[{hostname}] HostOutOfDiskSpace',
                        'body_re': (r'Summary: Host out of disk space(.*\n)+Instance: '
                                    fr'{hostname}(.*\n)+Job: node(.*\n)+Alert 1 of 1:(.*\n)+'),
                    }
                ], only_from=hostname)
            finally:
                host.check_output('rm -f bigfile')

            # Job missing alerts. The real version has a 4h trigger
            # duration, so we test on a shorter version.
            # cadvisor -> scrape -> prometheus -> alertmanager -> webhook
            email.clear()
            try:
                with host.shadow_file('/etc/pi-server/monitoring/rules.d/test.yml') as rules:
                    with host.sudo():
                        rules.write(jobmissing_alerts)
                        host.check_output('chmod a=r /etc/pi-server/monitoring/rules.d/test.yml')
                        host.check_output('pkill -HUP prometheus')  # reload rules
                        host.check_output('systemctl stop cron.service')
                        host.check_output(
                            'docker-compose -f /etc/pi-server/monitoring/docker-compose.yml stop '
                            'grafana')

                    time.sleep(300)  # absent takes a while to show up
                    email.assert_has_emails([
                        {
                            'from': f'notification@{hostname}.testbed',
                            'to': 'fake@fake.testbed',
                            'subject': f'[{hostname}] TestDockerJobMissing',
                            'body_re': (r'Summary: Grafana missing(.*\n)+Job: cadvisor(.*\n)+'
                                        r'Name: monitoring_grafana_1(.*\n)+Alert 1 of 1:(.*\n)+'),
                        },
                        {
                            'from': f'notification@{hostname}.testbed',
                            'to': 'fake@fake.testbed',
                            'subject': f'[{hostname}] TestSystemdJobMissing',
                            'body_re': (r'Summary: Cron missing(.*\n)+'
                                        r'Id: /system.slice/cron.service(.*\n)+'
                                        r'Job: cadvisor(.*\n)+'
                                        r'Alert 1 of 1:(.*\n)+'),
                        },
                    ], only_from=hostname)
            finally:
                with host.sudo():
                    host.check_output('pkill -HUP prometheus')  # reload rules
                    host.check_output('systemctl start cron.service')
                    host.check_output(
                        'docker-compose -f /etc/pi-server/monitoring/docker-compose.yml start '
                        'grafana')

    @for_host_types('pi', 'ubuntu')
    def test_cron(self, hostname: str, hosts: Dict[str, Host]) -> None:
        """This tests the cron system, not any particular cronjob."""
        host = hosts[hostname]
        journal = host.journal()
        service_unit_template = """[Unit]
Description=Fake service
After=network.target

[Service]
ExecStart=/bin/sleep 1h
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target
"""
        cron_unit_template = """[Service]
ExecStart=/etc/pi-server/cron/cron.d/{}
User={}
Group={}

[Install]
WantedBy=multi-user.target
"""
        cron_template = """#!/bin/bash
echo foo
source '/etc/pi-server/cron/cron-wrapper.bash' -u {} -c fake1 -c fake2
echo bar

{}
"""

        def check_state(
            service: str, running: bool = False, success: bool = False, failure: bool = False
        ) -> None:
            with host.sudo():
                lines = Lines(host.file(
                    f'/var/pi-server/monitoring/collect/cron-{service}-state.prom').content_string)
                assert lines.contains(
                    f'cron_state\\{{job="cron", cronjob="{service}", ' +
                    f'state="RUNNING"\\}} {int(running)}')
                assert lines.contains(
                    f'cron_state\\{{job="cron", cronjob="{service}", ' +
                    f'state="SUCCESS"\\}} {int(success)}')
                assert lines.contains(
                    f'cron_state\\{{job="cron", cronjob="{service}", ' +
                    f'state="FAILURE"\\}} {int(failure)}')

        try:
            with host.group_membership('vagrant', 'pi-server-monitoring-writers'), \
                    host.shadow_file('/etc/systemd/system/fake1.service') as fake1_unit, \
                    host.shadow_file('/etc/systemd/system/fake2.service') as fake2_unit, \
                    host.shadow_file(
                        '/etc/systemd/system/pi-server-cron-cron1.service') as cron1_unit, \
                    host.shadow_file(
                        '/etc/systemd/system/pi-server-cron-cron2.service') as cron2_unit, \
                    host.shadow_dir('/etc/pi-server/cron/cron.d') as cron_dir, \
                    host.shadow_dir('/etc/pi-server/cron/pause.d') as pause_dir, \
                    host.disable_login_emails():
                try:
                    with host.sudo():
                        fake1_unit.write(service_unit_template)
                        fake2_unit.write(service_unit_template)
                        cron1_unit.write(cron_unit_template.format('cron1', 'root', 'root'))
                        cron2_unit.write(cron_unit_template.format('cron2', 'vagrant', 'vagrant'))
                        host.check_output('systemctl daemon-reload')
                        host.check_output('systemctl start fake1.service')
                        host.check_output('systemctl start fake2.service')

                    fake1_service = host.service('fake1.service')
                    fake2_service = host.service('fake2.service')
                    runner = host.service('pi-server-cron.service')
                    cron1_service = host.service('pi-server-cron-cron1.service')
                    cron2_service = host.service('pi-server-cron-cron2.service')
                    assert fake1_service.is_running
                    assert fake2_service.is_running
                    assert not runner.is_running
                    assert not cron1_service.is_running
                    assert not cron2_service.is_running

                    with host.sudo():
                        pause_dir.file('fake1').write('')
                        pause_dir.file('fake2').write('')

                    cron1 = cron_dir.file('cron1')
                    cron2 = cron_dir.file('cron2')
                    with host.sudo():
                        cron1.write('')
                        cron2.write('')
                        host.check_output(f"chmod u=rwx,go=rx '{cron1.path}'")
                        host.check_output(f"chmod u=rwx,go=rx '{cron2.path}'")

                    # Successful run
                    with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir:
                        journal.clear()
                        run_stamp = 'good'
                        with host.sudo():
                            cron1.write(cron_template.format(
                                'root', f"sleep 5\necho 'cron1 {run_stamp}'"))
                            cron2.write(cron_template.format(
                                'vagrant', f"sleep 5\necho 'cron2 {run_stamp}'"))

                        with host.run_crons():
                            time.sleep(2)
                            assert not fake1_service.is_running
                            assert not fake2_service.is_running
                            check_state('cron-runner', running=True)

                        assert fake1_service.is_running
                        assert fake2_service.is_running
                        assert not runner.is_running
                        assert not cron1_service.is_running
                        assert not cron2_service.is_running

                        runner_log = journal.entries('pi-server-cron')
                        assert runner_log.count(r'.*ERROR.*') == 0
                        assert runner_log.count(r'.*WARNING.*') == 0
                        assert runner_log.count(r'.*FAILURE.*') == 0
                        assert runner_log.count(r'.*KILLED.*') == 0
                        assert runner_log.count(r'.*SUCCESS.*') == 1
                        assert runner_log.count(r"Stopped service 'fake1'") == 1
                        assert runner_log.count(r"Stopped service 'fake2'") == 1
                        assert runner_log.count(r"Started service 'fake1'") == 1
                        assert runner_log.count(r"Started service 'fake2'") == 1
                        assert runner_log.count(r'Running 2 script\(s\)') == 1
                        assert runner_log.count(r"RUNNING service 'pi-server-cron-cron1'") == 1
                        assert runner_log.count(r"RUNNING service 'pi-server-cron-cron2'") == 1
                        assert runner_log.count(
                            r"FINISHED RUNNING service 'pi-server-cron-cron1'") == 1
                        assert runner_log.count(
                            r"FINISHED RUNNING service 'pi-server-cron-cron2'") == 1
                        assert collect_dir.file(
                            'cron-cron-runner-state.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-start.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-stop.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-success.prom').user == 'pi-server-cron'
                        check_state('cron-runner', success=True)

                        cron1_log = journal.entries('pi-server-cron-cron1')
                        assert cron1_log.count(r'.*ERROR.*') == 0
                        assert cron1_log.count(r'.*WARNING.*') == 0
                        assert cron1_log.count(r'.*FAILURE.*') == 0
                        assert cron1_log.count(r'.*KILLED.*') == 0
                        assert cron1_log.count(r'.*SUCCESS.*') == 1
                        assert cron1_log.count(r'foo') == 2
                        assert cron1_log.count(r'bar') == 1
                        assert cron1_log.count(r'cron1 good') == 1
                        assert collect_dir.file('cron-cron1-state.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-start.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-stop.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-success.prom').user == 'root'
                        check_state('cron1', success=True)

                        cron2_log = journal.entries('pi-server-cron-cron2')
                        assert cron2_log.count(r'.*ERROR.*') == 0
                        assert cron2_log.count(r'.*WARNING.*') == 0
                        assert cron2_log.count(r'.*FAILURE.*') == 0
                        assert cron2_log.count(r'.*KILLED.*') == 0
                        assert cron2_log.count(r'.*SUCCESS.*') == 1
                        assert cron2_log.count(r'foo') == 2
                        assert cron2_log.count(r'bar') == 1
                        assert cron2_log.count(r'cron2 good') == 1
                        assert collect_dir.file('cron-cron2-state.prom').user == 'vagrant'
                        assert collect_dir.file('cron-cron2-start.prom').user == 'vagrant'
                        assert collect_dir.file('cron-cron2-stop.prom').user == 'vagrant'
                        assert collect_dir.file('cron-cron2-success.prom').user == 'vagrant'
                        check_state('cron2', success=True)

                    # Run with failures
                    with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir:
                        journal.clear()
                        run_stamp = 'bad'
                        with host.sudo():
                            cron1.write(cron_template.format(
                                'root', f"sleep 5\necho 'cron1 {run_stamp}'"))
                            cron2.write(cron_template.format(
                                'vagrant', f"sleep 5\necho 'cron2 {run_stamp}'\nfalse"))

                        with host.run_crons():
                            time.sleep(2)
                            assert not fake1_service.is_running
                            assert not fake2_service.is_running
                            check_state('cron-runner', running=True)

                        assert fake1_service.is_running
                        assert fake2_service.is_running
                        assert not runner.is_running
                        assert not cron1_service.is_running
                        assert not cron2_service.is_running

                        runner_log = journal.entries('pi-server-cron')
                        assert runner_log.count(r'.*ERROR.*') == 0
                        assert runner_log.count(r'.*WARNING.*') == 1
                        assert runner_log.count(r'.*FAILURE.*') == 0
                        assert runner_log.count(r'.*KILLED.*') == 0
                        assert runner_log.count(r'.*SUCCESS.*') == 1
                        assert runner_log.count(r"Stopped service 'fake1'") == 1
                        assert runner_log.count(r"Stopped service 'fake2'") == 1
                        assert runner_log.count(r"Started service 'fake1'") == 1
                        assert runner_log.count(r"Started service 'fake2'") == 1
                        assert runner_log.count(r'Running 2 script\(s\)') == 1
                        assert runner_log.count(r"RUNNING service 'pi-server-cron-cron1'") == 1
                        assert runner_log.count(r"RUNNING service 'pi-server-cron-cron2'") == 1
                        assert runner_log.count(
                            r"FINISHED RUNNING service 'pi-server-cron-cron1'") == 1
                        assert runner_log.count(
                            r".*service 'pi-server-cron-cron2' failed") == 1
                        assert collect_dir.file(
                            'cron-cron-runner-state.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-start.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-stop.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-success.prom').user == 'pi-server-cron'
                        check_state('cron-runner', success=True)

                        cron1_log = journal.entries('pi-server-cron-cron1')
                        assert cron1_log.count(r'.*ERROR.*') == 0
                        assert cron1_log.count(r'.*WARNING.*') == 0
                        assert cron1_log.count(r'.*FAILURE.*') == 0
                        assert cron1_log.count(r'.*KILLED.*') == 0
                        assert cron1_log.count(r'.*SUCCESS.*') == 1
                        assert cron1_log.count(r'foo') == 2
                        assert cron1_log.count(r'bar') == 1
                        assert cron1_log.count(r'cron1 bad') == 1
                        assert collect_dir.file('cron-cron1-state.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-start.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-stop.prom').user == 'root'
                        assert collect_dir.file('cron-cron1-success.prom').user == 'root'
                        check_state('cron1', success=True)

                        cron2_log = journal.entries('pi-server-cron-cron2')
                        assert cron2_log.count(r'.*ERROR.*') == 0
                        assert cron2_log.count(r'.*WARNING.*') == 0
                        assert cron2_log.count(r'.*FAILURE.*') == 2
                        assert cron2_log.count(r'.*KILLED.*') == 0
                        assert cron2_log.count(r'.*SUCCESS.*') == 0
                        assert cron2_log.count(r'foo') == 2
                        assert cron2_log.count(r'bar') == 1
                        assert cron2_log.count(r'cron2 bad') == 1
                        assert collect_dir.file('cron-cron2-state.prom').user == 'vagrant'
                        assert collect_dir.file('cron-cron2-start.prom').user == 'vagrant'
                        assert collect_dir.file('cron-cron2-stop.prom').user == 'vagrant'
                        assert not collect_dir.file('cron-cron2-success.prom').exists
                        check_state('cron2', failure=True)

                    # Disable running
                    with host.shadow_dir('/var/pi-server/monitoring/collect') as collect_dir, \
                            host.shadow_file('/etc/pi-server/cron/disabled'):
                        journal.clear()
                        run_stamp = 'disabled'
                        with host.sudo():
                            cron1.write(cron_template.format(
                                'root', f"sleep 5\necho 'cron1 {run_stamp}'"))
                            cron2.write(cron_template.format(
                                'vagrant', f"sleep 5\necho 'cron2 {run_stamp}'"))

                        with host.run_crons():
                            pass

                        assert fake1_service.is_running
                        assert fake2_service.is_running
                        assert not runner.is_running
                        assert not cron1_service.is_running
                        assert not cron2_service.is_running

                        runner_log = journal.entries('pi-server-cron')
                        assert runner_log.count(r'.*ERROR.*') == 1
                        assert runner_log.count(r'.*WARNING.*') == 0
                        assert runner_log.count(r'.*FAILURE.*') == 2
                        assert runner_log.count(r'.*KILLED.*') == 0
                        assert runner_log.count(r'.*SUCCESS.*') == 0
                        assert runner_log.count(r'ERROR: running is disabled') == 1
                        assert collect_dir.file(
                            'cron-cron-runner-state.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-start.prom').user == 'pi-server-cron'
                        assert collect_dir.file(
                            'cron-cron-runner-stop.prom').user == 'pi-server-cron'
                        assert not collect_dir.file('cron-cron-runner-success.prom').exists
                        check_state('cron-runner', failure=True)

                        cron1_log = journal.entries('pi-server-cron-cron1')
                        assert not cron1_log
                        assert not collect_dir.file('cron-cron1-state.prom').exists
                        assert not collect_dir.file('cron-cron1-start.prom').exists
                        assert not collect_dir.file('cron-cron1-stop.prom').exists
                        assert not collect_dir.file('cron-cron1-success.prom').exists

                        cron2_log = journal.entries('pi-server-cron-cron2')
                        assert not cron2_log
                        assert not collect_dir.file('cron-cron2-state.prom').exists
                        assert not collect_dir.file('cron-cron2-start.prom').exists
                        assert not collect_dir.file('cron-cron2-stop.prom').exists
                        assert not collect_dir.file('cron-cron2-success.prom').exists

                finally:
                    # Cleanup
                    with host.sudo():
                        host.check_output('systemctl stop fake1.service')
                        host.check_output('systemctl stop fake2.service')

                    assert not fake1_service.is_running
                    assert not fake2_service.is_running
                    assert not runner.is_running
                    assert not cron1_service.is_running
                    assert not cron2_service.is_running
        finally:
            with host.sudo():
                host.check_output('systemctl daemon-reload')

    @for_host_types('pi', 'ubuntu')
    def test_updates(
            self, hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        internet = hosts['internet']
        known_packages = []

        def check_state(updated: int, not_updated: int) -> None:
            with host.sudo():
                lines = Lines(host.file(
                    '/var/pi-server/monitoring/collect/updates.prom').content_string)
                assert lines.contains(f'apt_packages_upgraded\\{{job="updates"\\}} {updated}')
                assert lines.contains(
                    f'apt_packages_not_upgraded\\{{job="updates"\\}} {not_updated}')

        try:
            with host.shadow_file('/etc/apt/sources.list') as sources_list:
                internet.check_output('aptly repo add main aptly/pi-server-test_1_all.deb')
                internet.check_output('aptly publish update main')
                known_packages.append('pi-server-test')

                with host.sudo():
                    sources_list.write(
                        'deb [trusted=yes check-date=no date-max-future=86400] ' +
                        f'http://{addrs["internet"]}:8080/ main main')
                    host.check_output('apt-get update')
                    host.check_output('apt-get install pi-server-test')

                # Nothing to update
                with host.run_crons(disable_sources_list=False):
                    pass

                assert host.package('pi-server-test').is_installed
                assert host.package('pi-server-test').version == '1'
                assert not host.package('pi-server-test2').is_installed
                check_state(0, 0)

                # One package to update
                internet.check_output('aptly repo add main aptly/pi-server-test_1.1_all.deb')
                internet.check_output('aptly publish update main')

                with host.run_crons(disable_sources_list=False):
                    pass

                assert host.package('pi-server-test').is_installed
                assert host.package('pi-server-test').version == '1.1'
                assert not host.package('pi-server-test2').is_installed
                check_state(1, 0)

                # One not upgraded
                internet.check_output('aptly repo add main aptly/pi-server-test_1.2_all.deb')
                internet.check_output('aptly repo add main aptly/pi-server-test2_1_all.deb')
                internet.check_output('aptly publish update main')
                known_packages.append('pi-server-test2')

                with host.run_crons(disable_sources_list=False):
                    pass

                assert host.package('pi-server-test').is_installed
                assert host.package('pi-server-test').version == '1.1'
                assert not host.package('pi-server-test2').is_installed
                check_state(0, 1)

                # Manual dist-upgrade
                with host.sudo():
                    host.check_output('apt-get -y dist-upgrade')

                # Nothing to update
                with host.run_crons(disable_sources_list=False):
                    pass

                assert host.package('pi-server-test').is_installed
                assert host.package('pi-server-test').version == '1.2'
                assert host.package('pi-server-test2').is_installed
                assert host.package('pi-server-test2').version == '1'
                check_state(0, 0)

        finally:
            # Cleanup
            with host.sudo():
                host.check_output(f'apt-get -y remove {" ".join(known_packages)}')

            internet.check_output("aptly repo remove main 'Name (% *)'")
            internet.check_output('aptly publish update main')

            with host.sudo():
                host.check_output('apt-get update')

import time
from typing import Dict, List, Tuple
from testinfra.host import Host
from conftest import Email, Lines, Net, Vagrant, corresponding_hostname, for_host_types


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

    # @for_host_types('pi', 'ubuntu')
    # def test_04_vars(self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
    #     host = hosts[hostname]
    #     assert host.file('/etc/pi-server/lan-ip').content_string.strip() == addrs[hostname]
    #     assert host.file('/etc/pi-server/lan-iface').content_string.strip() == 'enp0s8'
    #     assert host.file('/etc/pi-server/fqdn').content_string.strip() == hostname + '.testbed'

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
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] SSH login: vagrant from %s' % (hostname, client_ip),
                'body_re': (r'(.*\n)*PAM_USER=vagrant\n(.*\n)*PAM_RHOST=%s\n(.*\n)*' %
                            client_ip.replace('.', r'\.')),
            },
            {
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] foo' % hostname,
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
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] foo' % hostname,
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

#     @for_host_types('pi', 'ubuntu')
#     def test_09_cron(self, hostname: str, hosts: Dict[str, Host], email: Email) -> None:
#         """This tests the cron system, not any particular cronjob."""
#         host = hosts[hostname]
#         systemd_template = """[Unit]
# Description=Fake service
# After=network.target

# [Service]
# ExecStart=/bin/sleep 1h
# Restart=always
# User=root
# Group=root

# [Install]
# WantedBy=multi-user.target
# """
#         try:
#             with host.shadow_file('/etc/systemd/system/fake1.service') as fake1_file, \
#                  host.shadow_file('/etc/systemd/system/fake2.service') as fake2_file, \
#                  host.shadow_dir('/etc/pi-server/cron/cron-normal.d') as normal_dir, \
#                  host.shadow_dir('/etc/pi-server/cron/cron-safe.d') as safe_dir, \
#                  host.shadow_dir('/etc/pi-server/cron/pause-on-cron.d') as pause_dir, \
#                  host.shadow_file('/etc/pi-server/cron/last-run.log') as safe_log_file, \
#                  host.shadow_file('/cron-test-normal-output') as normal_out, \
#                  host.disable_login_emails():
#                 try:
#                     with host.sudo():
#                         fake1_file.write(systemd_template)
#                         fake2_file.write(systemd_template)
#                         host.check_output('systemctl daemon-reload')
#                         host.check_output('systemctl start fake1.service')
#                         host.check_output('systemctl start fake2.service')

#                     fake1_service = host.service('fake1.service')
#                     fake2_service = host.service('fake2.service')
#                     assert fake1_service.is_running
#                     assert fake2_service.is_running

#                     with host.sudo():
#                         pause_dir.file('fake1.service').write('')
#                         pause_dir.file('fake2.service').write('')

#                     safe_cron1 = safe_dir.file('safe1')
#                     safe_cron2 = safe_dir.file('safe2')
#                     normal_cron = normal_dir.file('normal')

#                     # Successful run
#                     email.clear()
#                     run_stamp = 'good'
#                     with host.sudo():
#                         safe_cron1.write('sleep 5\necho \'safe1 %s\' >> "${LOG}"' % run_stamp)
#                         safe_cron2.write('sleep 5\necho \'safe2 %s\' >> "${LOG}"' % run_stamp)
#                         normal_cron.write('#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'' % (
#                             run_stamp, normal_out.path))
#                         host.check_output('chmod a+x %s' % normal_cron.path)

#                     with host.run_crons():
#                         time.sleep(2)
#                         assert not fake1_service.is_running
#                         assert not fake2_service.is_running

#                     assert fake1_service.is_running
#                     assert fake2_service.is_running

#                     safe_log = Lines(safe_log_file.content_string)
#                     assert safe_log.contains(r'Stopping services...')
#                     assert safe_log.contains(r'Stopped services$')
#                     assert safe_log.contains(r"STARTED 'safe1' at .*")
#                     assert safe_log.contains(r'safe1 good')
#                     assert safe_log.contains(r"FINISHED 'safe1' at .*")
#                     assert safe_log.contains(r"STARTED 'safe2' at .*")
#                     assert safe_log.contains(r'safe2 good')
#                     assert safe_log.contains(r"FINISHED 'safe2' at .*")
#                     assert safe_log.contains(r'Starting services...')
#                     assert safe_log.contains(r'Started services')

#                     assert normal_out.content_string == 'normal good\n'

#                     time.sleep(15)
#                     email.assert_emails([], only_from=hostname)

#                     # Run with failures
#                     email.clear()
#                     run_stamp = 'bad'
#                     with host.sudo():
#                         safe_cron1.write(
#                             'sleep 5\necho \'safe1 %s\' >> "${LOG}"\necho \'safe1 echo\''
#                             % run_stamp)
#                         safe_cron2.write(
#                             'sleep 5\necho \'safe2 %s\' >> "${LOG}"\nfalse' % run_stamp)
#                         normal_cron.write(
#                             ('#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'\necho '
#                              '\'normal echo\'') % (run_stamp, normal_out.path))

#                     with host.run_crons():
#                         time.sleep(2)
#                         assert not fake1_service.is_running
#                         assert not fake2_service.is_running

#                     assert fake1_service.is_running
#                     assert fake2_service.is_running

#                     safe_log = Lines(safe_log_file.content_string)
#                     assert safe_log.contains(r'Stopping services...')
#                     assert safe_log.contains(r'Stopped services$')
#                     assert safe_log.contains(r"STARTED 'safe1' at .*")
#                     assert safe_log.contains(r'safe1 bad')
#                     assert safe_log.contains(r"FINISHED 'safe1' at .*")
#                     assert safe_log.contains(r"STARTED 'safe2' at .*")
#                     assert safe_log.contains(r'safe2 bad')
#                     assert not safe_log.contains(r"FINISHED 'safe2' at .*")
#                     assert safe_log.contains(r"Couldn't run safe2\.")
#                     assert safe_log.contains(r'Starting services...')
#                     assert safe_log.contains(r'Started services')

#                     assert normal_out.content_string == 'normal bad\n'

#                     time.sleep(15)
#                     email.assert_emails([
#                         {
#                             'from': 'notification@%s.testbed' % hostname,
#                             'to': 'fake@fake.testbed',
#                             'subject': '[%s] Cron failed' % hostname,
#                             'body_re': r"Couldn't run safe2.\n\n",
#                         },
#                         {
#                             'from': '',
#                             'to': '',
#                             'subject': (('Cron <root@%s> test -x /usr/sbin/anacron || '
#                                          '( cd / && run-parts --report /etc/cron.daily )')
#                                         % hostname),
#                             'body_re': r"/etc/cron.daily/pi-server:\nsafe1 echo\nnormal echo\n",
#                         },
#                     ], only_from=hostname)

#                     # Disable running
#                     with host.shadow_file('/etc/pi-server/cron/cron-disabled'):
#                         email.clear()
#                         run_stamp = 'disabled'
#                         with host.sudo():
#                             safe_log_file.clear()
#                             normal_out.clear()
#                             safe_cron1.write('sleep 5\necho \'safe1 %s\' >> "${LOG}"' % run_stamp)
#                             safe_cron2.write('sleep 5\necho \'safe2 %s\' >> "${LOG}"' % run_stamp)
#                             normal_cron.write(
#                                 '#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'' % (
#                                     run_stamp, normal_out.path))

#                         with host.run_crons():
#                             pass

#                         assert fake1_service.is_running
#                         assert fake2_service.is_running
#                         assert safe_log_file.content_string == '\n'
#                         assert normal_out.content_string == '\n'

#                         time.sleep(15)
#                         email.assert_emails([], only_from=hostname)
#                 finally:
#                     # Cleanup
#                     with host.sudo():
#                         host.check_output('systemctl stop fake1.service')
#                         host.check_output('systemctl stop fake2.service')

#                     assert not fake1_service.is_running
#                     assert not fake2_service.is_running
#         finally:
#             with host.sudo():
#                 host.check_output('systemctl daemon-reload')

#     @for_host_types('pi', 'ubuntu')
#     def test_10_automatic_updates(
#             self, hostname: str,
#             hosts: Dict[str, Host],
#             addrs: Dict[str, str],
#             email: Email) -> None:
#         host = hosts[hostname]
#         internet = hosts['internet']
#         known_packages = []

#         try:
#             with host.shadow_file('/etc/apt/sources.list') as sources_list, \
#                  host.disable_login_emails():
#                 internet.check_output('aptly repo add main aptly/pi-server-test_1_all.deb')
#                 internet.check_output('aptly publish update main')
#                 known_packages.append('pi-server-test')

#                 with host.sudo():
#                     sources_list.write(
#                         ('deb [trusted=yes check-date=no date-max-future=86400] '
#                          'http://%s:8080/ main main') % addrs['internet'])
#                     host.check_output('apt-get update')
#                     host.check_output('apt-get install pi-server-test')

#                 # Nothing to update
#                 email.clear()
#                 with host.run_crons(disable_sources_list=False):
#                     pass

#                 assert host.package('pi-server-test').is_installed
#                 assert host.package('pi-server-test').version == '1'
#                 assert not host.package('pi-server-test2').is_installed
#                 email.assert_emails([], only_from=hostname)

#                 # One package to update
#                 internet.check_output('aptly repo add main aptly/pi-server-test_1.1_all.deb')
#                 internet.check_output('aptly publish update main')

#                 email.clear()
#                 with host.run_crons(disable_sources_list=False):
#                     pass

#                 assert host.package('pi-server-test').is_installed
#                 assert host.package('pi-server-test').version == '1.1'
#                 assert not host.package('pi-server-test2').is_installed
#                 email.assert_emails([{
#                     'from': 'notification@%s.testbed' % hostname,
#                     'to': 'fake@fake.testbed',
#                     'subject': '[%s] Installed 1 update' % hostname,
#                     'body_re': (r"(.*\n)*1 upgraded, 0 newly installed, "
#                                 r"0 to remove and 0 not upgraded.\n(.*\n)*"),
#                 }], only_from=hostname)

#                 # One not upgraded
#                 internet.check_output('aptly repo add main aptly/pi-server-test_1.2_all.deb')
#                 internet.check_output('aptly repo add main aptly/pi-server-test2_1_all.deb')
#                 internet.check_output('aptly publish update main')
#                 known_packages.append('pi-server-test2')

#                 email.clear()
#                 with host.run_crons(disable_sources_list=False):
#                     pass

#                 assert host.package('pi-server-test').is_installed
#                 assert host.package('pi-server-test').version == '1.1'
#                 assert not host.package('pi-server-test2').is_installed
#                 email.assert_emails([{
#                     'from': 'notification@%s.testbed' % hostname,
#                     'to': 'fake@fake.testbed',
#                     'subject': '[%s] 1 package not updated' % hostname,
#                     'body_re': (r"(.*\n)*0 upgraded, 0 newly installed, "
#                                 r"0 to remove and 1 not upgraded.\n(.*\n)*"),
#                 }], only_from=hostname)

#                 # Manual dist-upgrade
#                 with host.sudo():
#                     host.check_output('apt-get -y dist-upgrade')

#                 # Nothing to update
#                 email.clear()
#                 with host.run_crons(disable_sources_list=False):
#                     pass

#                 assert host.package('pi-server-test').is_installed
#                 assert host.package('pi-server-test').version == '1.2'
#                 assert host.package('pi-server-test2').is_installed
#                 assert host.package('pi-server-test2').version == '1'
#                 email.assert_emails([], only_from=hostname)

#         finally:
#             # Cleanup
#             with host.sudo():
#                 host.check_output('apt-get -y remove %s' % ' '.join(known_packages))

#             internet.check_output("aptly repo remove main 'Name (% *)'")
#             internet.check_output('aptly publish update main')

#             with host.sudo():
#                 host.check_output('apt-get update')

#     @for_host_types('pi', 'ubuntu')
#     def test_11_disk_usage(
#             self, hostname: str,
#             hosts: Dict[str, Host],
#             email: Email) -> None:
#         host = hosts[hostname]

#         with host.disable_login_emails():
#             # Lots of space
#             email.clear()
#             with host.run_crons():
#                 pass

#             email.assert_emails([], only_from=hostname)

#             # Not much space
#             try:
#                 host.make_bigfile('bigfile', '/')

#                 email.clear()
#                 with host.run_crons():
#                     pass

#                 email.assert_emails([{
#                     'from': 'notification@%s.testbed' % hostname,
#                     'to': 'fake@fake.testbed',
#                     'subject': '[%s] Storage space alert' % hostname,
#                     'body_re': (r'A partition is above 90% full.\n(.*\n)*'
#                                 r'(/dev/sda1|/dev/mapper/vagrant--vg-root).*9[0-9]%.*/\n(.*\n)*'),
#                 }], only_from=hostname)
#             finally:
#                 host.check_output('rm -f bigfile')

#             # Lots of space again
#             email.clear()
#             with host.run_crons():
#                 pass

#             email.assert_emails([], only_from=hostname)

#     @for_host_types('pi', 'ubuntu')
#     def test_12_nginx(self, hostname: str, hosts: Dict[str, Host]) -> None:
#         """This just installs the nginx service, not any sites."""
#         host = hosts[hostname]
#         assert host.service('nginx').is_enabled
#         assert host.service('nginx').is_running

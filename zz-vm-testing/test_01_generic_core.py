import time
from typing import Dict, List, Tuple
from testinfra.host import Host
from conftest import Email, Lines, Net, Vagrant, corresponding_hostname, for_host_types


class Test01GenericCore:
    @for_host_types('pi')
    def test_00_base_config(self, hostname: str, hosts: Dict[str, Host]) -> None:
        lines = Lines(hosts[hostname].check_output('debconf-show locales'), hostname)
        assert lines.contains(r'[^a-zA-Z]*locales/locales_to_be_generated: en_GB.UTF-8 UTF-8')
        assert lines.contains(r'[^a-zA-Z]*locales/default_environment_locale: en_GB.UTF-8')

    @for_host_types('pi')
    def test_01_packages(self, hostname: str, hosts: Dict[str, Host]) -> None:
        # We pick one of the packages that the script installs, that isn't installed by default.
        assert hosts[hostname].package('etckeeper').is_installed

    # 02-pi-new-user is a no-op in the testbed.

    @for_host_types('pi')
    def test_03_cleanup_users(self, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        # We pick the most important user - root - and a few that are changed
        with host.sudo():
            assert host.user('root').password == '!'
            assert host.user('systemd-timesync').shell == '/usr/sbin/nologin'
            assert host.user('systemd-timesync').password == '!*'
            assert host.user('messagebus').shell == '/usr/sbin/nologin'
            assert host.user('messagebus').password == '!*'

    @for_host_types('pi')
    def test_04_vars(self, hostname: str, hosts: Dict[str, Host], addrs: Dict[str, str]) -> None:
        host = hosts[hostname]
        assert host.file('/etc/pi-server/lan-ip').content_string.strip() == addrs[hostname]
        assert host.file('/etc/pi-server/lan-iface').content_string.strip() == 'eth1'
        assert host.file('/etc/pi-server/fqdn').content_string.strip() == hostname + '.testbed'
        assert (host.file('/etc/pi-server/email-target').content_string.strip() ==
                'fake@fake.testbed')
        assert (host.file('/etc/pi-server/email-smtp-server').content_string.strip() ==
                addrs['internet'])
        assert host.file('/etc/pi-server/email-smtp-port').content_string.strip() == '1025'

    # 05-network is tested by test_base's reachability and routing tests.

    @for_host_types('pi')
    def test_06_email(self, email: Email, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        client_ip = host.client_ip()

        email.clear()

        # SSH login emails are on by default, so we expect one email for logging in, and one for
        # the command we actually ran.
        host.check_output('/etc/pi-server/send-notification-email foo bar')
        email.assert_emails([
            {
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] SSH login: vagrant from %s' % (hostname, client_ip),
                'body_re': r'PAM_USER=vagrant\nPAM_RHOST=%s\n(.*\n)*' % client_ip.replace(
                    '.', r'\.'),
            },
            {
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] foo' % hostname,
                'body_re': r'bar\n\n',
            },
        ])

        # Disable SSH login emails from our address, and we should only get one email.
        with host.disable_login_emails():
            email.clear()

            host.check_output('/etc/pi-server/send-notification-email foo bar')
            email.assert_emails([
                {
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] foo' % hostname,
                    'body_re': r'bar\n\n',
                },
            ])

    # 07-sshd is partially tested by the fact we can still log in at all, and partially
    # by the email-at-login behaviour.

    @for_host_types('pi')
    def test_08_firewall(
            self, vagrant: Vagrant, net: Net, hostname: str, hosts: Dict[str, Host]) -> None:
        host = hosts[hostname]
        port_script = '/etc/pi-server/firewall/port'

        def is_open(port: int, protocol: str) -> bool:
            cmd = host.run('%s is-open %d %s' % (port_script, port, protocol))
            return cmd.rc == 0 and cmd.stdout == 'Yes\n'

        def is_closed(port: int, protocol: str) -> bool:
            cmd = host.run('%s is-open %d %s' % (port_script, port, protocol))
            return cmd.rc == 1 and cmd.stdout == 'No\n'

        def opens_at_boot(port: int, protocol: str) -> bool:
            cmd = host.run('%s opens-at-boot %d %s' % (port_script, port, protocol))
            return cmd.rc == 0 and cmd.stdout == 'Yes\n'

        def doesnt_open_at_boot(port: int, protocol: str) -> bool:
            cmd = host.run('%s opens-at-boot %d %s' % (port_script, port, protocol))
            return cmd.rc == 1 and cmd.stdout == 'No\n'

        with host.shadow_file('/etc/pi-server/firewall/iptables-tcp-open-boot'), \
             host.shadow_file('/etc/pi-server/firewall/iptables-udp-open-boot'):
            # Base state - only hardcoded ports open at boot
            vagrant.reboot(hostname)
            net.assert_ports_open(
                {corresponding_hostname(hostname, 'router'): {
                    hostname: {'tcp': {22}, 'udp': set()}}})

            # Port validation
            assert host.check_output('%s is-valid 0' % port_script) == 'Yes'
            assert host.check_output('%s is-valid 1234' % port_script) == 'Yes'
            assert host.check_output('%s is-valid 65535' % port_script) == 'Yes'
            host.run_expect([1], '%s is-valid -1' % port_script)
            host.run_expect([1], '%s is-valid 65536' % port_script)
            host.run_expect([1], '%s is-valid a' % port_script)
            host.run_expect([1], '%s is-valid 10a' % port_script)
            host.run_expect([1], '%s is-valid' % port_script)

            # Protocol validation
            assert host.check_output('%s is-valid 1234 tcp' % port_script) == 'Yes'
            assert host.check_output('%s is-valid 1234 udp' % port_script) == 'Yes'
            host.run_expect([1], '%s is-valid 1234 foo' % port_script)

            # Run servers on the ports we're interested in
            host.check_output('tmux new-session -s s1 -d nc -l -p 1995')
            host.check_output('tmux new-session -s s2 -d nc -l -k -u -p 1996')
            host.check_output('tmux new-session -s s3 -d nc -l -p 1997')
            host.check_output('tmux new-session -s s4 -d nc -l -p 1998')
            host.check_output('tmux new-session -s s5 -d nc -l -k -u -p 1999')

            # Base state
            assert is_open(22, 'tcp') # hardcoded
            assert is_closed(22, 'udp')
            assert is_closed(1995, 'tcp')
            assert is_closed(1996, 'udp')
            assert is_closed(1997, 'tcp')
            assert is_closed(1998, 'tcp')
            assert is_closed(1999, 'udp')

            assert doesnt_open_at_boot(22, 'tcp') # hardcoded
            assert doesnt_open_at_boot(22, 'udp')
            assert doesnt_open_at_boot(1995, 'tcp')
            assert doesnt_open_at_boot(1996, 'udp')
            assert doesnt_open_at_boot(1997, 'tcp')
            assert doesnt_open_at_boot(1998, 'tcp')
            assert doesnt_open_at_boot(1999, 'udp')

            # Open and close at runtime
            host.check_output('%s open 1997 tcp' % port_script)
            host.check_output('%s open 1997 tcp' % port_script) # idempotent
            host.check_output('%s open 1998 tcp' % port_script)
            host.check_output('%s open 1999 udp' % port_script)
            host.check_output('%s close 1997 tcp' % port_script)

            assert is_open(22, 'tcp') # hardcoded
            assert is_closed(22, 'udp')
            assert is_closed(1995, 'tcp')
            assert is_closed(1996, 'udp')
            assert is_closed(1997, 'tcp')
            assert is_open(1998, 'tcp')
            assert is_open(1999, 'udp')

            host.run_expect([1], '%s close 1997 tcp' % port_script) # extra close does nothing

            assert is_open(22, 'tcp') # hardcoded
            assert is_closed(22, 'udp')
            assert is_closed(1995, 'tcp')
            assert is_closed(1996, 'udp')
            assert is_closed(1997, 'tcp')
            assert is_open(1998, 'tcp')
            assert is_open(1999, 'udp')

            net.assert_ports_open({
                corresponding_hostname(hostname, 'router'): {
                    hostname: {
                        'tcp': {22, 1998},
                        'udp': set(), # for some reason this can't detect the open UDP port
                    }
                }
            })

            # File manipulation
            assert doesnt_open_at_boot(22, 'tcp') # hardcoded
            assert doesnt_open_at_boot(22, 'udp')
            assert doesnt_open_at_boot(1995, 'tcp')
            assert doesnt_open_at_boot(1996, 'udp')
            assert doesnt_open_at_boot(1997, 'tcp')
            assert doesnt_open_at_boot(1998, 'tcp')
            assert doesnt_open_at_boot(1999, 'udp')

            host.check_output('%s open-at-boot 1995 tcp' % port_script)
            host.check_output('%s open-at-boot 1996 udp' % port_script)
            host.check_output('%s open-at-boot 1997 tcp' % port_script)
            host.check_output('%s open-at-boot 1997 tcp' % port_script) # idempotent
            host.check_output('%s dont-open-at-boot 1997 tcp' % port_script)

            assert doesnt_open_at_boot(22, 'tcp') # hardcoded
            assert doesnt_open_at_boot(22, 'udp')
            assert opens_at_boot(1995, 'tcp')
            assert opens_at_boot(1996, 'udp')
            assert doesnt_open_at_boot(1997, 'tcp')
            assert doesnt_open_at_boot(1998, 'tcp')
            assert doesnt_open_at_boot(1999, 'udp')

            host.check_output(
                '%s dont-open-at-boot 1997 tcp' % port_script) # extra don't open does nothing

            assert doesnt_open_at_boot(22, 'tcp') # hardcoded
            assert doesnt_open_at_boot(22, 'udp')
            assert opens_at_boot(1995, 'tcp')
            assert opens_at_boot(1996, 'udp')
            assert doesnt_open_at_boot(1997, 'tcp')
            assert doesnt_open_at_boot(1998, 'tcp')
            assert doesnt_open_at_boot(1999, 'udp')

            assert is_open(22, 'tcp') # hardcoded
            assert is_closed(22, 'udp')
            assert is_closed(1995, 'tcp')
            assert is_closed(1996, 'udp')
            assert is_closed(1997, 'tcp')
            assert is_open(1998, 'tcp')
            assert is_open(1999, 'udp')

            # Check that open at boot works
            vagrant.reboot(hostname)

            host.check_output('tmux new-session -s s1 -d nc -l -p 1995')
            host.check_output('tmux new-session -s s2 -d nc -l -k -u -p 1996')
            host.check_output('tmux new-session -s s3 -d nc -l -p 1997')
            host.check_output('tmux new-session -s s4 -d nc -l -p 1998')
            host.check_output('tmux new-session -s s5 -d nc -l -k -u -p 1999')

            assert doesnt_open_at_boot(22, 'tcp') # hardcoded
            assert doesnt_open_at_boot(22, 'udp')
            assert opens_at_boot(1995, 'tcp')
            assert opens_at_boot(1996, 'udp')
            assert doesnt_open_at_boot(1997, 'tcp')
            assert doesnt_open_at_boot(1998, 'tcp')
            assert doesnt_open_at_boot(1999, 'udp')

            assert is_open(22, 'tcp') # hardcoded
            assert is_closed(22, 'udp')
            assert is_open(1995, 'tcp')
            assert is_open(1996, 'udp')
            assert is_closed(1997, 'tcp')
            assert is_closed(1998, 'tcp')
            assert is_closed(1999, 'udp')

            net.assert_ports_open({
                corresponding_hostname(hostname, 'router'): {
                    hostname: {
                        'tcp': {22, 1995},
                        'udp': set(), # for some reason this can't detect the open UDP port
                    }
                }
            })

        # Restore original state
        vagrant.reboot(hostname)

    @for_host_types('pi')
    def test_09_cron(self, hostname: str, hosts: Dict[str, Host], email: Email) -> None:
        """This tests the cron system, not any particular cronjob."""
        host = hosts[hostname]
        systemd_template = """[Unit]
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
        with host.shadow_file('/etc/systemd/system/fake1.service') as fake1_file, \
             host.shadow_file('/etc/systemd/system/fake2.service') as fake2_file, \
             host.shadow_dir('/etc/pi-server/cron/cron-normal.d') as normal_dir, \
             host.shadow_dir('/etc/pi-server/cron/cron-safe.d') as safe_dir, \
             host.shadow_dir('/etc/pi-server/cron/pause-on-cron.d') as pause_dir, \
             host.shadow_file('/etc/pi-server/cron/last-run.log') as safe_log_file, \
             host.shadow_file('/cron-test-normal-output') as normal_out, \
             host.disable_login_emails():
            with host.sudo():
                fake1_file.write(systemd_template)
                fake2_file.write(systemd_template)
                host.check_output('systemctl daemon-reload')
                host.check_output('systemctl start fake1.service')
                host.check_output('systemctl start fake2.service')

            fake1_service = host.service('fake1.service')
            fake2_service = host.service('fake2.service')
            assert fake1_service.is_running
            assert fake2_service.is_running

            with host.sudo():
                pause_dir.file('fake1.service').write('')
                pause_dir.file('fake2.service').write('')

            safe_cron1 = safe_dir.file('safe1')
            safe_cron2 = safe_dir.file('safe2')
            normal_cron = normal_dir.file('normal')

            # Successful run
            email.clear()
            run_stamp = 'good'
            with host.sudo():
                safe_cron1.write('sleep 5\necho \'safe1 %s\' >> "${LOG}"' % run_stamp)
                safe_cron2.write('sleep 5\necho \'safe2 %s\' >> "${LOG}"' % run_stamp)
                normal_cron.write('#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'' % (
                    run_stamp, normal_out.path))
                host.check_output('chmod a+x %s' % normal_cron.path)

            with host.run_crons():
                time.sleep(5)
                assert not fake1_service.is_running
                assert not fake2_service.is_running

            assert fake1_service.is_running
            assert fake2_service.is_running

            safe_log = Lines(safe_log_file.content_string)
            assert safe_log.contains(r'Stopping services...')
            assert safe_log.contains(r'Stopped services$')
            assert safe_log.contains(r"STARTED 'safe1' at .*")
            assert safe_log.contains(r'safe1 good')
            assert safe_log.contains(r"FINISHED 'safe1' at .*")
            assert safe_log.contains(r"STARTED 'safe2' at .*")
            assert safe_log.contains(r'safe2 good')
            assert safe_log.contains(r"FINISHED 'safe2' at .*")
            assert safe_log.contains(r'Starting services...')
            assert safe_log.contains(r'Started services')

            assert normal_out.content_string == 'normal good\n'

            time.sleep(15)
            email.assert_emails([])

            # Run with failures
            email.clear()
            run_stamp = 'bad'
            with host.sudo():
                safe_cron1.write(
                    'sleep 5\necho \'safe1 %s\' >> "${LOG}"\necho \'safe1 echo\'' % run_stamp)
                safe_cron2.write('sleep 5\necho \'safe2 %s\' >> "${LOG}"\nfalse' % run_stamp)
                normal_cron.write(
                    '#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'\necho \'normal echo\'' %
                    (run_stamp, normal_out.path))

            with host.run_crons():
                time.sleep(5)
                assert not fake1_service.is_running
                assert not fake2_service.is_running

            assert fake1_service.is_running
            assert fake2_service.is_running

            safe_log = Lines(safe_log_file.content_string)
            assert safe_log.contains(r'Stopping services...')
            assert safe_log.contains(r'Stopped services$')
            assert safe_log.contains(r"STARTED 'safe1' at .*")
            assert safe_log.contains(r'safe1 bad')
            assert safe_log.contains(r"FINISHED 'safe1' at .*")
            assert safe_log.contains(r"STARTED 'safe2' at .*")
            assert safe_log.contains(r'safe2 bad')
            assert not safe_log.contains(r"FINISHED 'safe2' at .*")
            assert safe_log.contains(r"Couldn't run safe2\.")
            assert safe_log.contains(r'Starting services...')
            assert safe_log.contains(r'Started services')

            assert normal_out.content_string == 'normal bad\n'

            time.sleep(15)
            email.assert_emails([
                {
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] Cron failed' % hostname,
                    'body_re': r"Couldn't run safe2.\n\n",
                },
                {
                    'from': '',
                    'to': '',
                    'subject': (('Cron <root@%s> test -x /usr/sbin/anacron || '
                                 '( cd / && run-parts --report /etc/cron.daily )') % hostname),
                    'body_re': r"/etc/cron.daily/pi-server:\nsafe1 echo\nnormal echo\n",
                },
            ])

            # Disable running
            with host.shadow_file('/etc/pi-server/cron/cron-disabled'):
                email.clear()
                run_stamp = 'disabled'
                with host.sudo():
                    safe_log_file.clear()
                    normal_out.clear()
                    safe_cron1.write('sleep 5\necho \'safe1 %s\' >> "${LOG}"' % run_stamp)
                    safe_cron2.write('sleep 5\necho \'safe2 %s\' >> "${LOG}"' % run_stamp)
                    normal_cron.write(
                        '#!/bin/bash\nsleep 5\necho \'normal %s\' > \'%s\'' % (
                            run_stamp, normal_out.path))

                with host.run_crons():
                    pass

                assert fake1_service.is_running
                assert fake2_service.is_running
                assert safe_log_file.content_string == '\n'
                assert normal_out.content_string == '\n'

                time.sleep(15)
                email.assert_emails([])

            # Cleanup
            with host.sudo():
                host.check_output('systemctl stop fake1.service')
                host.check_output('systemctl stop fake2.service')

            assert not fake1_service.is_running
            assert not fake2_service.is_running

        with host.sudo():
            host.check_output('systemctl daemon-reload')

    @for_host_types('pi')
    def test_10_automatic_updates(
            self, hostname: str,
            hosts: Dict[str, Host],
            addrs: Dict[str, str],
            email: Email) -> None:
        host = hosts[hostname]
        internet = hosts['internet']

        with host.shadow_file('/etc/apt/sources.list') as sources_list, \
             host.disable_login_emails():
            internet.check_output('aptly repo add main aptly/pi-server-test_1_all.deb')
            internet.check_output('aptly publish update main')

            with host.sudo():
                sources_list.write(
                    'deb [trusted=yes] http://%s:8080/ main main' % addrs['internet'])
                host.check_output('apt-get update')
                host.check_output('apt-get install pi-server-test')

            # Nothing to update
            email.clear()
            with host.run_crons():
                pass

            assert host.package('pi-server-test').is_installed
            assert host.package('pi-server-test').version == '1'
            assert not host.package('pi-server-test2').is_installed
            email.assert_emails([])

            # One package to update
            internet.check_output('aptly repo add main aptly/pi-server-test_1.1_all.deb')
            internet.check_output('aptly publish update main')

            email.clear()
            with host.run_crons():
                pass

            assert host.package('pi-server-test').is_installed
            assert host.package('pi-server-test').version == '1.1'
            assert not host.package('pi-server-test2').is_installed
            email.assert_emails([{
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] Installed 1 update' % hostname,
                'body_re': (r"(.*\n)*1 upgraded, 0 newly installed, "
                            r"0 to remove and 0 not upgraded.\n(.*\n)*"),
            }])

            # One not upgraded
            internet.check_output('aptly repo add main aptly/pi-server-test_1.2_all.deb')
            internet.check_output('aptly repo add main aptly/pi-server-test2_1_all.deb')
            internet.check_output('aptly publish update main')

            email.clear()
            with host.run_crons():
                pass

            assert host.package('pi-server-test').is_installed
            assert host.package('pi-server-test').version == '1.1'
            assert not host.package('pi-server-test2').is_installed
            email.assert_emails([{
                'from': 'notification@%s.testbed' % hostname,
                'to': 'fake@fake.testbed',
                'subject': '[%s] 1 package not updated' % hostname,
                'body_re': (r"(.*\n)*0 upgraded, 0 newly installed, "
                            r"0 to remove and 1 not upgraded.\n(.*\n)*"),
            }])

            # Manual dist-upgrade
            with host.sudo():
                host.check_output('apt-get -y dist-upgrade')

            # Nothing to update
            email.clear()
            with host.run_crons():
                pass

            assert host.package('pi-server-test').is_installed
            assert host.package('pi-server-test').version == '1.2'
            assert host.package('pi-server-test2').is_installed
            assert host.package('pi-server-test2').version == '1'
            email.assert_emails([])

            # Cleanup
            with host.sudo():
                host.check_output('apt-get -y remove pi-server-test pi-server-test2')

            internet.check_output("aptly repo remove main 'Name (% *)'")
            internet.check_output('aptly publish update main')

        with host.sudo():
            host.check_output('apt-get update')

    @for_host_types('pi')
    def test_11_disk_usage(
            self, hostname: str,
            hosts: Dict[str, Host],
            email: Email) -> None:
        host = hosts[hostname]

        with host.disable_login_emails():
            # Lots of space
            email.clear()
            with host.run_crons():
                pass

            email.assert_emails([])

            # Not much space
            output = host.check_output('df --output=size,used / | tail -n 1')
            # Sizes in kiB
            size = int(output.split()[0])
            used = int(output.split()[1])
            # Want to get it up to 92% full
            needed = int(0.92 * size) - used
            try:
                host.check_output('dd if=/dev/zero of=bigfile bs=1M count=%d' % int(needed / 1024))

                email.clear()
                with host.run_crons():
                    pass

                email.assert_emails([{
                    'from': 'notification@%s.testbed' % hostname,
                    'to': 'fake@fake.testbed',
                    'subject': '[%s] Storage space alert' % hostname,
                    'body_re': r'A partition is above 90% full.\n(.*\n)*/dev/sda1.*/\n(.*\n)*',
                }])
            finally:
                host.check_output('rm -f bigfile')

            # Lots of space again
            email.clear()
            with host.run_crons():
                pass

            email.assert_emails([])

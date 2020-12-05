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
        client_ip = host.check_output('echo "${SSH_CLIENT}"').split()[0]
        with host.shadow_file('/etc/pi-server/ssh-email-on-login-exceptions') as f:
            email.clear()

            # SSH login emails are on by default, so we expect one email for logging in, and one for
            # the command we actually ran.
            host.check_output('/etc/pi-server/send-notification-email foo bar')
            email.assert_emails([
                {
                    'from': 'notification@%s.testbed' % hostname,
                    'subject': '[%s] SSH login: vagrant from %s' % (hostname, client_ip),
                    'body_re': r'PAM_USER=vagrant\nPAM_RHOST=%s\n(.*\n)*' % client_ip.replace(
                        '.', r'\.'),
                },
                {
                    'from': 'notification@%s.testbed' % hostname,
                    'subject': '[%s] foo' % hostname,
                    'body_re': r'bar\n\n',
                },
            ])

            # Disable SSH login emails from our address, and we should only get one email.
            with host.sudo():
                f.write('vagrant:%s' % client_ip)
            email.clear()

            host.check_output('/etc/pi-server/send-notification-email foo bar')
            email.assert_emails([
                {
                    'from': 'notification@%s.testbed' % hostname,
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
    def test_09_cron(self, hostname: str, hosts: Dict[str, Host]) -> None:
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
        log = host.file('/etc/pi-server/cron/last-run.log')

        with host.shadow_file('/etc/systemd/system/fake1.service') as fake1_file, \
             host.shadow_file('/etc/systemd/system/fake2.service') as fake2_file, \
             host.shadow_dir('/etc/pi-server/cron/cron-normal.d') as normal_dir, \
             host.shadow_dir('/etc/pi-server/cron/cron-safe.d') as safe_dir, \
             host.shadow_dir('/etc/pi-server/cron/pause-on-cron.d') as pause_dir:
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

            # TODO add tests

            with host.sudo():
                host.check_output('systemctl stop fake1.service')
                host.check_output('systemctl stop fake2.service')

            assert not fake1_service.is_running
            assert not fake2_service.is_running

        with host.sudo():
            host.check_output('systemctl daemon-reload')

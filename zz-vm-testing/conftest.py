from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple, TypeVar, cast)
import datetime
import inspect
import ipaddress
import json
import logging
import os.path
import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from urllib.parse import urlparse, ParseResult
import codetiming
import pytest
import requests
import trparse
import vagrant as vagrant_lib
from _pytest.fixtures import FixtureRequest
from _pytest.mark.structures import MarkDecorator
from _pytest.python import Metafunc
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from testinfra.modules.file import File
from testinfra.host import Host
from testinfra.utils import ansible_runner
from tidylib import tidy_document


T = TypeVar('T')
_ANSIBLE_RUNNER = ansible_runner.AnsibleRunner(
    '.vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory')


def _file_write(self: File, content: str) -> None:
    self.check_output('echo \'%s\' > %s' % (content, self.path))

File.write = _file_write # type: ignore


def _file_clear(self: File) -> None:
    self.write('')

File.clear = _file_clear # type: ignore


class Timer(codetiming.Timer):

    def __init__(self, name: str = '[unnamed timer]') -> None:
        super().__init__(name=name, logger=logging.debug)
        self._args = []  # type: List[str]
        self._retval = None  # type: object
        self._extra_text = []  # type: List[object]

    @staticmethod
    def _escape_str(s: str) -> str:
        return s.replace('{', '{{').replace('}', '}}')

    def _update_text(self) -> None:
        first_line = '\u001b[1;36m{name}'
        if self._args:
            first_line += '(' + ', '.join(self._args) + ')'
        first_line += '\u001b[0m: elapsed time: {:.4f} seconds'

        msg = ''
        if self._extra_text:
            for item in self._extra_text:
                msg += Timer._escape_str(str(item)) + '\n'
        if self._retval is not None:
            msg += 'Result: ' + Timer._escape_str(str(self._retval))
        msg = '\n'.join(['    ' + line for line in msg.split('\n') if line])
        if msg:
            msg = '\n' + msg
        self.text = first_line + msg

    def set_args(self, *args: Any) -> None:
        self._args = [Timer._escape_str(str(arg)) for arg in args]

    def set_retval(self, retval: object) -> None:
        self._retval = retval

    def add_extra(self, extra: object) -> None:
        self._extra_text.append(extra)

    def __enter__(self) -> 'Timer':
        return cast(Timer, super().__enter__())

    def __exit__(self, *exc_info: Any) -> None:
        self._update_text()
        super().__exit__(*exc_info)

    def __call__(self, *args: Any) -> Any:  # pylint: disable=arguments-differ
        raise NotImplementedError("Do not use 'Timer' as a decorator, use 'timer' instead")


def timer(f: Callable[..., T]) -> Callable[..., T]:
    arg_details = OrderedDict(inspect.signature(f).parameters)
    has_self = 'self' in arg_details
    if has_self:
        del arg_details['self']
    inject = arg_details and list(arg_details.values())[0].annotation == Timer

    @wraps(f)
    def inner(*args: Any, **kwargs: Any) -> T:
        with Timer(f.__qualname__) as t:
            t.set_args(*(args[1:] if has_self else args))
            if inject and has_self:
                retval = f(*((args[0], t) + args[1:]), **kwargs)
            elif inject:
                retval = f(t, *args, **kwargs)
            else:
                retval = f(*args, **kwargs)
            t.set_retval(retval)
            return retval
    return inner


def vms_down(*args: str) -> MarkDecorator:
    return pytest.mark.vms_down(vms=args)


class Vagrant:
    @timer
    def __init__(self) -> None:
        super().__init__()
        self._v = vagrant_lib.Vagrant()
        # VM operations are slow, so we cache the state. If state is modified externally, run
        # rescan_state to update the cache.
        self._state = {} # type: Dict[str, bool]
        self.rescan_state()

    def rescan_state(self) -> None:
        self._state = {vm.name: vm.state == self._v.RUNNING for vm in self._v.status()}

    def state(self) -> Dict[str, bool]:
        return self._state

    def all_vms(self) -> List[str]:
        return sorted(self._state)

    def running_vms(self) -> List[str]:
        return sorted([vm for vm, up in self._state.items() if up])

    @timer
    def up(self, vm: str) -> None:
        if not self._state[vm]:
            self._v.up(vm_name=vm)
            self._state[vm] = True

    @timer
    def down(self, vm: str) -> None:
        if self._state[vm]:
            self._v.halt(vm_name=vm)
            self._state[vm] = False

    @timer
    def reboot(self, *vms: str) -> None:
        for vm in vms:
            self.down(vm)
            self.up(vm)
        time.sleep(60)

    def set_state(self, vm: str, state: bool) -> None:
        if state:
            self.up(vm)
        else:
            self.down(vm)

    def set_states(self, vms_down: Sequence[str] = ()) -> bool:
        old_state = self.running_vms()
        for vm in self.all_vms():
            self.set_state(vm, vm not in vms_down)
        return self.running_vms() != old_state


class AddrInNet:
    def __init__(self, mask: str) -> None:
        super().__init__()
        self._mask = mask
        self._net = ipaddress.IPv4Network(mask)

    def __eq__(self, other: object) -> bool:
        return ipaddress.IPv4Address(other) in self._net

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return 'AddrInNet(%s)' % self._mask


class Net:
    def __init__(self, hosts: Dict[str, Host], addrs: Dict[str, str], vagrant: Vagrant) -> None:
        super().__init__()
        self._hosts = hosts
        self._addrs = addrs
        self._vagrant = vagrant

    @timer
    def reachable(self, host: str, addr: str) -> bool:
        return self._hosts[host].addr(self._addrs[addr]).is_reachable

    @timer
    def traceroute(self, t: Timer, host: str, addr: str) -> List[str]:
        """Gets the hops from host to addr; empty list means unreachable."""
        result = trparse.loads(
            self._hosts[host].check_output('sudo traceroute -I %s', self._addrs[addr]))
        for hop in result.hops:
            for probe in hop.probes:
                if probe.annotation:
                    return []
        out = []
        for hop in result.hops:
            ips = set()
            for probe in hop.probes:
                if probe.ip:
                    ips.add(probe.ip)
            if len(ips) == 1:
                out.append(list(ips)[0])
            elif len(ips) > 1:
                raise ValueError('Traceroute %s -> %s returned multiple IPs: %s' % (
                    host, addr, ips))
            else:
                # Traceroute returned '*'
                out.append('')

        # A failure is a failure, regardless of where it tried to go in the meantime
        if addr != 'external' and out[-1] != self._addrs[addr]:
            return []

        t.add_extra(result)
        return out

    @timer
    def nmap(self, t: Timer, host: str, addr: str) -> Dict[str, Set[int]]:
        """Gets the open ports on addr as seen from host."""
        result = self._hosts[host].check_output(
            'sudo nmap -p-2000 --open -Pn -oN - -T4 -sU -sS %s' % self._addrs[addr])
        udp = set()
        tcp = set()
        for line in result.split('\n'):
            match = re.match('^([0-9]+)/(tcp|udp) +([^ ]+)', line)
            if match is not None:
                port = int(match.group(1))
                protocol = match.group(2)
                state = match.group(3).split('|')
                if 'open' in state:
                    if protocol == 'udp':
                        udp.add(port)
                    elif protocol == 'tcp':
                        tcp.add(port)
                    else:
                        raise ValueError("nmap returned an unknown protocol '%s'" % protocol)
        t.add_extra(result)
        return {'tcp': tcp, 'udp': udp}

    def _host_addr_pairs(self, hosts: List[str]) -> List[Tuple[str, str]]:
        running_vms = self._vagrant.running_vms()
        if sorted(hosts) != running_vms:
            raise ValueError(
                ("'hosts' must exactly match the running VMs: got %s, want %s. Either the wrong "
                 "hosts were passed in , or some VMs are in the wrong state.") % (
                     sorted(hosts), running_vms))

        out = []
        for host in sorted(hosts):
            for addr in sorted(self._addrs):
                out.append((host, addr))
        return out

    def _assert_result(
            self,
            want_fn: Callable[[str, str], object],
            got_fn: Callable[[str, str], object],
            host_addr_pairs: List[Tuple[str, str]]) -> None:
        expected = [want_fn(host, addr) for host, addr in host_addr_pairs]
        logging.debug('Running %d checks', len(host_addr_pairs))
        with ThreadPoolExecutor() as e:
            results = e.map(got_fn, *zip(*host_addr_pairs))
        incorrect = []
        for pair, want, got in zip(host_addr_pairs, expected, results):
            if want != got:
                host, addr = pair
                incorrect.append((host, addr, want, got))
        if incorrect:
            lines = ['%s gave the wrong result for the following host/addr combinations:' %
                     got_fn.__name__]
            for host, addr, want, got in incorrect:
                lines.append('  %s -> %s (%s): want %s, got %s' % (
                    host, addr, self._addrs[addr], want, got))
            pytest.fail('\n'.join(lines))

    @timer
    def assert_reachability(self, reachable: Dict[str, List[str]]) -> None:
        """Verify reachability of all host/addr pairs is as expected.

        Args:
          reachable: mapping from hostname to addr names that should be reachable
            from that host. All host/addr pairs not listed will be checked for
            being unreachable.
        """
        self._assert_result(
            lambda host, addr: addr in reachable[host],
            self.reachable,
            self._host_addr_pairs(sorted(reachable)))

    @timer
    def assert_routes(self, routes: Dict[str, Dict[str, List[object]]]) -> None:
        """Verify routes between all host/addr pairs are as expected.

        Args:
          routes: mapping from host to target addr to intermediate hops (i.e. not including the
          target itself), for all addrs that should be reachable from host. All host/addr pairs
          not listed will be checked for being unreachable.
        """
        def traceroute(host: str, addr: str) -> List[str]:
            result = self.traceroute(host, addr)  # pylint: disable=no-value-for-parameter
            if addr == 'external' and result:
                # External is a special case, in that we don't care where the packets go once they
                # leave the testbed.
                new_result = []
                for hop in result:
                    if hop not in self._addrs.values():
                        break
                    new_result.append(hop)
                result = new_result + [self._addrs[addr]]
            return result

        self._assert_result(
            lambda host, addr: [(self._addrs[hop] if isinstance(hop, str) else hop) for hop in
                                (routes[host][addr] + [addr] if addr in routes[host] else [])],
            traceroute,
            self._host_addr_pairs(sorted(routes)))

    @timer
    def assert_ports_open(self, ports: Dict[str, Dict[str, Dict[str, Set[int]]]]) -> None:
        """Check that only the given ports are open for the given host/addr pairs."""
        host_addr_pairs = []
        for host in ports:
            for addr in ports[host]:
                host_addr_pairs.append((host, addr))
        self._assert_result(
            lambda host, addr: ports[host][addr],
            self.nmap,
            host_addr_pairs)


class Email:
    _PORT = 1080

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host

    def clear(self) -> None:
        # SSH login emails are sent asynchronously so they don't delay login. So we
        # sleep to allow login emails from previous tests to arrive before clearing.
        time.sleep(5)
        r = requests.delete('http://%s:%d/api/emails' % (self._host, self._PORT))
        r.raise_for_status()

    def assert_emails(self, emails: List[Dict[str, str]], only_from: Optional[str] = None) -> None:
        r = requests.get('http://%s:%d/api/emails' % (self._host, self._PORT))
        r.raise_for_status()
        got_emails = r.json()
        if only_from:
            got_emails = [
                e for e in got_emails
                if e['from']['value'][0]['address'] == 'notification@%s.testbed' % only_from
                or not e['from']['value'][0]['address']]

        if len(got_emails) != len(emails):
            raise ValueError(
                'Length of want and got differ (%d vs %d); all emails:\n%s' %
                (len(emails), len(got_emails), json.dumps(got_emails, sort_keys=True, indent=2)))
        for email, expected in zip(sorted(got_emails, key=lambda e: cast(str, e['subject'])),
                                   sorted(emails, key=lambda e: e['subject'])):
            # pylint: disable=cell-var-from-loop
            def fail(field_name: str, want: str, got: str) -> None:
                pytest.fail(
                    ("Email field '%s' doesn't match: want:\n%s\ngot:\n%s\n"
                     "full want:\n%s\nfull got:\n%s") % (
                         field_name, want, got, str(expected),
                         json.dumps(email, sort_keys=True, indent=2)))

            def check_field(field_name: str, want: str, got: str) -> None:
                if want != got:
                    fail(field_name, want, got)

            check_field('to', expected['to'], email['to']['value'][0]['address'])
            check_field('from', expected['from'], email['from']['value'][0]['address'])
            check_field('subject', expected['subject'], email['subject'])

            if re.fullmatch(expected['body_re'], email['text']) is None:
                fail('text', expected['body_re'], email['text'])


class MockServer:
    _PORT = 443
    _CATCH_ALL = {
        'httpRequest': {},
        'httpResponse': {
            'statusCode': 404,
            'body': 'Mockserver fallback',
        },
        'priority': -10,
    }

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host
        self._expectations = [] # type: List[str]

    def clear(self) -> None:
        self._expectations = []
        r = requests.put('http://%s:%d/reset' % (self._host, self._PORT))
        r.raise_for_status()

        # Catch-all expectation
        r = requests.put('http://%s:%d/expectation' % (self._host, self._PORT),
                         json=self._CATCH_ALL)
        r.raise_for_status()

    def expect(self, json: Dict[Any, Any]) -> None:
        json['times'] = {'remainingTimes': 1}
        r = requests.put('http://%s:%d/expectation' % (self._host, self._PORT), json=json)
        r.raise_for_status()
        self._expectations.append(r.json()[0]['httpRequest'])

    def assert_called(self, times: int = 1) -> None:
        for request in self._expectations:
            r = requests.put('http://%s:%d/verify' % (self._host, self._PORT), json={
                'httpRequest': request,
                'times': {
                    'atLeast': times,
                    'atMost': times,
                },
            })
            r.raise_for_status()

    def assert_not_called(self) -> None:
        self.assert_called(0)


class ShadowFile:
    """Creates an empty file in place of path; restores path's contents on exit.

    This lets tests modify the file's content without messing up the original
    content. Shadow persists across reboots.
    """
    def __init__(self, host: Host, path: str) -> None:
        super().__init__()
        self._host = host
        self._path = path
        self._path_existed = False
        self._backup_path = self._path + '.backup'
        self._backup_file = self._host.file(self._backup_path)

    def __enter__(self) -> File:
        f = self._host.file(self._path)
        self._path_existed = f.exists

        if self._path_existed:
            if self._backup_file.exists:
                raise ValueError(
                    ("Cannot shadow '%s' because backup file '%s' already "
                     "exists. Fix it manually.") % (
                         self._path, self._backup_path))
            with self._host.sudo():
                self._host.check_output(
                    'cp -p %s %s' % (self._path, self._backup_path))
        else:
            with self._host.sudo():
                self._host.check_output('touch %s' % self._path)

        with self._host.sudo():
            f.clear()
        return f

    def __exit__(self, *exc_info: Any) -> None:
        if self._path_existed:
            if self._backup_file.exists:
                with self._host.sudo():
                    self._host.check_output('mv %s %s' % (self._backup_path, self._path))
        else:
            with self._host.sudo():
                self._host.check_output('rm %s' % self._path)


def _host_shadow_file(self: Host, path: str) -> ShadowFile:
    return ShadowFile(self, path)

Host.shadow_file = _host_shadow_file # type: ignore


class ShadowDir:
    """Creates an empty dir in place of path; restores path's contents on exit.

    This lets tests modify the dir's content without messing up the original
    content. Shadow does not persist across reboots.
    """
    def __init__(self, host: Host, path: str) -> None:
        super().__init__()
        self._host = host
        self._path = path
        self._tmpdir = None # type: Optional[str]

    def __enter__(self) -> 'ShadowDir':
        with self._host.sudo():
            tmpdir = self._host.check_output('mktemp -d')
            self._host.check_output(
                'chown --reference=%s %s' % (self._path, tmpdir))
            self._host.check_output(
                'chmod --reference=%s %s' % (self._path, tmpdir))
            self._host.check_output(
                'mount --bind %s %s' % (tmpdir, self._path))
            self._tmpdir = tmpdir
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._tmpdir:
            with self._host.sudo():
                self._host.check_output('umount %s' % self._path)
                self._host.check_output('rm -r %s' % self._tmpdir)

    def file(self, path: str) -> File:
        return self._host.file(os.path.join(self._path, path))


def _host_shadow_dir(self: Host, path: str) -> ShadowDir:
    return ShadowDir(self, path)

Host.shadow_dir = _host_shadow_dir # type: ignore


def _host_client_ip(self: Host) -> str:
    return self.check_output('echo "${SSH_CLIENT}"').split()[0]

Host.client_ip = _host_client_ip # type: ignore


def _host_make_bigfile(self: Host, path: str, mount_point: str) -> None:
    output = self.check_output('df --output=size,used %s | tail -n 1' % mount_point)
    # Sizes in kiB
    size = int(output.split()[0])
    used = int(output.split()[1])
    # Want to get it up to 92% full
    needed = int(0.92 * size) - used
    self.check_output('dd if=/dev/zero of=%s bs=1M count=%d' % (path, int(needed / 1024)))

Host.make_bigfile = _host_make_bigfile # type: ignore


@contextmanager
def _host_disable_login_emails(self: Host) -> Iterator[None]:
    client_ip = self.client_ip()
    with self.shadow_file('/etc/pi-server/ssh-email-on-login-exceptions') as f:
        with self.sudo():
            f.write('vagrant:%s' % client_ip)
        yield

Host.disable_login_emails = _host_disable_login_emails # type: ignore


@contextmanager
def _host_mount_backup_dir(self: Host) -> Iterator[None]:
    try:
        with self.sudo():
            self.check_output('mount /mnt/backup')
        yield
    finally:
        with self.sudo():
            self.check_output('umount /mnt/backup')

Host.mount_backup_dir = _host_mount_backup_dir # type: ignore


class CronRunner:
    def __init__(
            self, host: Host,
            time: str,
            cmd_to_watch: str,
            disable_sources_list: bool,
            date: str) -> None:
        super().__init__()
        self._host = host
        self._time = time
        self._date = date
        self._cmd_to_watch = cmd_to_watch
        self._disable_sources_list = disable_sources_list
        self._restore_guest_additions = False
        self._sources_list = None # type: Optional[ShadowFile]

    def __enter__(self) -> None:
        with self._host.sudo():
            if self._disable_sources_list:
                self._sources_list = self._host.shadow_file('/etc/apt/sources.list')
                self._sources_list.__enter__()
            if self._host.service('vboxadd-service').is_running:
                self._host.check_output('systemctl stop vboxadd-service')
                self._restore_guest_additions = True
            self._host.check_output('timedatectl set-ntp false')
            # Large change to override cron's daylight-saving-time handling
            self._host.check_output(
                "timedatectl set-time '%s 09:00:00'" % self._date)
            time.sleep(90)
            # Wait for it to start
            self._host.check_output(
                "timedatectl set-time '%s %s'" % (self._date, self._time))
        self._host.check_output(
            ("timeout 60 bash -c "
             "\"while ! pgrep -x -f '%s'; do true; done\"; true") % self._cmd_to_watch)

    def __exit__(self, *exc_info: Any) -> None:
        # Wait for cron to finish
        self._host.check_output(
            "while pgrep -x -f '%s'; do true; done" % self._cmd_to_watch)
        with self._host.sudo():
            self._host.check_output('timedatectl set-ntp true')
            if self._restore_guest_additions:
                self._host.check_output('systemctl start vboxadd-service')
            if self._sources_list:
                self._sources_list.__exit__(None)


def _host_run_crons(
        self: Host,
        time: str = '02:24:50',
        cmd_to_watch: str = '/bin/bash /etc/cron.daily/pi-server',
        disable_sources_list: bool = True,
        date: str = datetime.date.today().isoformat()) -> CronRunner:
    return CronRunner(self, time, cmd_to_watch, disable_sources_list, date)

Host.run_crons = _host_run_crons # type: ignore


class Lines:
    def __init__(self, s: str, name: Optional[str] = None) -> None:
        super().__init__()
        self._lines = s.split('\n')
        self._name = name

    def contains(self, pattern: str) -> bool:
        for line in self._lines:
            if re.fullmatch(pattern, line) is not None:
                return True
        return False

    def __repr__(self) -> str:
        out = '['
        if self._name:
            out += self._name + ' '
        out += '(%d lines)]' % len(self._lines)
        return out


class WebDriver(Firefox):
    def validate_html(self) -> None:
        errors = tidy_document(self.page_source, options={'show-warnings':0})[1]
        assert not errors

    def validate_links(self) -> Set[ParseResult]:
        this_addr = urlparse(self.current_url).hostname

        def elems(tag: str) -> List[Any]:
            e = cast(List[Any], self.find_elements(By.TAG_NAME, tag))
            assert e
            return e

        for e in elems('link'):
            assert urlparse(e.get_attribute('href')).hostname == this_addr

        for e in elems('img'):
            assert urlparse(e.get_attribute('src')).hostname == this_addr

        same = set()
        other = set()
        for e in elems('a'):
            url = urlparse(e.get_attribute('href'))
            if url.hostname == this_addr:
                same.add(url)
            else:
                other.add(url)
        assert same
        return other


class OpenVPN:
    def __init__(self, hosts: Dict[str, Host], vagrant: Vagrant) -> None:
        super().__init__()
        self._hosts = hosts
        self._vagrant = vagrant

    @contextmanager
    def connect(self, hostname: str, config: str, other_host: str) -> Iterator[None]:
        try:
            self._hosts[hostname].check_output(
                'tmux new-session -s s1 -d sudo openvpn --config /etc/openvpn/%s' % config)
            time.sleep(20)
            yield
        finally:
            # OpenVPN doesn't clean up after itself properly, so just reboot
            self._vagrant.reboot(hostname, other_host)


def _hostnames() -> List[str]:
    """Returns all host names from the ansible inventory."""
    return sorted(_ANSIBLE_RUNNER.get_hosts())


def _host_type(hostname: str) -> str:
    match = re.fullmatch(r'([^0-9]+)[0-9]*', hostname)
    if match is None:
        raise ValueError("Can't find host type for host '%s'" % hostname)
    return match.group(1)


def host_number(hostname: str) -> str:
    match = re.fullmatch(r'[^0-9]+([0-9]*)', hostname)
    if match is None:
        raise ValueError("Can't find host number for host '%s'" % hostname)
    return match.group(1)


def _hostnames_by_type() -> Dict[str, List[str]]:
    out = {} # type: Dict[str, List[str]]
    for hostname in _hostnames():
        out.setdefault(_host_type(hostname), []).append(hostname)
    for value in out.values():
        value.sort()
    return out


def corresponding_hostname(hostname: str, host_type: str) -> str:
    num = host_number(hostname)
    if num:
        return host_type + num
    return 'internet'


@pytest.fixture(scope='session')
def hosts() -> Dict[str, Host]:
    """Returns all hosts by name from the ansible inventory."""
    return {name: _ANSIBLE_RUNNER.get_host(
        name, ssh_config='ssh_config') for name in _hostnames()}


@pytest.fixture(scope='session')
def hosts_by_type(hosts: Dict[str, Host]) -> Dict[str, List[Tuple[str, Host]]]:
    out = {} # type: Dict[str, List[Tuple[str, Host]]]
    for host_type, hostnames in _hostnames_by_type().items():
        out[host_type] = [(hostname, hosts[hostname]) for hostname in hostnames]
    return out


def for_hosts(*args: str) -> MarkDecorator:
    if not args:
        raise ValueError('Input to for_hosts must be non-empty')
    return pytest.mark.for_hosts(hosts=args)


def for_host_types(*args: str) -> MarkDecorator:
    hostnames = []
    hostnames_by_type = _hostnames_by_type()
    for host_type in args:
        hostnames += hostnames_by_type[host_type]
    return for_hosts(*hostnames)


@pytest.fixture(scope='session')
def addrs() -> Dict[str, str]:
    """Returns all IP addresses by name."""
    with open('config.json') as f:
        return cast(Dict[str, str], json.load(f)['addrs'])


@pytest.fixture(scope='session')
def masks() -> Dict[str, str]:
    """Returns all net masks by name."""
    with open('config.json') as f:
        return cast(Dict[str, str], json.load(f)['masks'])


@pytest.fixture(scope='session')
def vagrant() -> Vagrant:
    return Vagrant()


@pytest.fixture(scope='session')
def net(hosts: Dict[str, Host], addrs: Dict[str, str], vagrant: Vagrant) -> Net:
    return Net(hosts, addrs, vagrant)


@pytest.fixture(scope='session')
def openvpn(hosts: Dict[str, Host], vagrant: Vagrant) -> OpenVPN:
    return OpenVPN(hosts, vagrant)


@pytest.fixture()
def email(addrs: Dict[str, str]) -> Email:
    e = Email(addrs['internet'])
    e.clear()
    return e


@pytest.fixture()
def mockserver(addrs: Dict[str, str]) -> MockServer:
    m = MockServer(addrs['internet'])
    m.clear()
    return m


@pytest.fixture(scope='function', autouse=True)
@timer
def ensure_vm_state(vagrant: Vagrant, request: FixtureRequest) -> None:
    vms_down = ()  # type: Tuple[str, ...]
    for mark in request.keywords.get('pytestmark', []):
        if mark.name == 'vms_down':
            vms_down = mark.kwargs['vms']
    if vagrant.set_states(vms_down):
        time.sleep(30)


def pytest_generate_tests(metafunc: Metafunc) -> None:
    marker = metafunc.definition.get_closest_marker('for_hosts')
    if marker:
        metafunc.parametrize('hostname', marker.kwargs['hosts'])

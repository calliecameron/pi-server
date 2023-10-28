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
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    cast,
)
from urllib.parse import ParseResult, urlparse

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
from testinfra.host import Host
from testinfra.modules.file import File
from testinfra.utils import ansible_runner
from tidylib import tidy_document

T = TypeVar("T")
_ANSIBLE_RUNNER = ansible_runner.AnsibleRunner(
    ".vagrant/provisioners/ansible/inventory/vagrant_ansible_inventory"
)


def _file_write(self: File, content: str) -> None:
    self.check_output(f"echo '{content}' > {self.path}")


File.write = _file_write  # type: ignore


def _file_clear(self: File) -> None:
    self.write("")


File.clear = _file_clear  # type: ignore


class Timer(codetiming.Timer):
    def __init__(self, name: str = "[unnamed timer]") -> None:
        super().__init__(name=name, logger=logging.debug)
        self._args = []  # type: List[str]
        self._retval = None  # type: object
        self._extra_text = []  # type: List[object]

    @staticmethod
    def _escape_str(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    def _update_text(self) -> None:
        first_line = "\u001b[1;36m{name}"
        if self._args:
            first_line += "(" + ", ".join(self._args) + ")"
        first_line += "\u001b[0m: elapsed time: {:.4f} seconds"

        msg = ""
        if self._extra_text:
            for item in self._extra_text:
                msg += Timer._escape_str(str(item)) + "\n"
        if self._retval is not None:
            msg += "Result: " + Timer._escape_str(str(self._retval))
        msg = "\n".join(["    " + line for line in msg.split("\n") if line])
        if msg:
            msg = "\n" + msg
        self.text = first_line + msg

    def set_args(self, *args: Any) -> None:
        self._args = [Timer._escape_str(str(arg)) for arg in args]

    def set_retval(self, retval: object) -> None:
        self._retval = retval

    def add_extra(self, extra: object) -> None:
        self._extra_text.append(extra)

    def __enter__(self) -> "Timer":
        return cast(Timer, super().__enter__())

    def __exit__(self, *exc_info: Any) -> None:
        self._update_text()
        super().__exit__(*exc_info)

    def __call__(self, *args: Any) -> Any:  # pylint: disable=arguments-differ
        raise NotImplementedError("Do not use 'Timer' as a decorator, use 'timer' instead")


def timer(f: Callable[..., T]) -> Callable[..., T]:
    arg_details = OrderedDict(inspect.signature(f).parameters)
    has_self = "self" in arg_details
    if has_self:
        del arg_details["self"]
    inject = arg_details and list(arg_details.values())[0].annotation == Timer

    @wraps(f)
    def inner(*args: Any, **kwargs: Any) -> T:
        with Timer(f.__qualname__) as t:
            t.set_args(*(args[1:] if has_self else args))  # pylint: disable=no-member
            if inject and has_self:
                retval = f(*((args[0], t) + args[1:]), **kwargs)
            elif inject:
                retval = f(t, *args, **kwargs)
            else:
                retval = f(*args, **kwargs)
            t.set_retval(retval)  # pylint: disable=no-member
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
        self._state = {}  # type: Dict[str, bool]
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

    def set_states(
        self, vms_down: Sequence[str] = ()  # pylint: disable=redefined-outer-name
    ) -> bool:
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
        return f"AddrInNet({self._mask})"


class Net:
    def __init__(
        # pylint: disable=redefined-outer-name
        self,
        hosts: Dict[str, Host],
        addrs: Dict[str, str],
        vagrant: Vagrant,
    ) -> None:
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
            self._hosts[host].check_output("sudo traceroute -I %s", self._addrs[addr])
        )
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
                raise ValueError(f"Traceroute {host} -> {addr} returned multiple IPs: {ips}")
            else:
                # Traceroute returned '*'
                out.append("")

        # A failure is a failure, regardless of where it tried to go in the meantime
        if addr != "external" and out[-1] != self._addrs[addr]:
            return []

        t.add_extra(result)
        return out

    @timer
    def nmap(
        self, t: Timer, host: str, addr: str, ranges: List[Tuple[int, int]]
    ) -> Dict[str, Set[int]]:
        """Gets the open ports on addr as seen from host."""
        ports = ",".join([f"{a}-{b}" for (a, b) in ranges])
        result = self._hosts[host].check_output(
            f"sudo nmap -p{ports} --open -Pn -oN - -T4 -sU -sS " + self._addrs[addr]
        )
        udp = set()
        tcp = set()
        for line in result.split("\n"):
            match = re.match("^([0-9]+)/(tcp|udp) +([^ ]+)", line)
            if match is not None:
                port = int(match.group(1))
                protocol = match.group(2)
                state = match.group(3).split("|")
                if "open" in state:
                    if protocol == "udp":
                        udp.add(port)
                    elif protocol == "tcp":
                        tcp.add(port)
                    else:
                        raise ValueError(f"nmap returned an unknown protocol '{protocol}'")
        t.add_extra(result)
        return {"tcp": tcp, "udp": udp}

    def _host_addr_pairs(
        self, hosts: List[str]  # pylint: disable=redefined-outer-name
    ) -> List[Tuple[str, str]]:
        running_vms = self._vagrant.running_vms()
        if sorted(hosts) != running_vms:
            raise ValueError(
                (
                    f"'hosts' must exactly match the running VMs: got {sorted(hosts)}, want "
                    f"{running_vms}. Either the wrong hosts were passed in , or some VMs are in "
                    "the wrong state."
                )
            )

        out = []
        for host in sorted(hosts):
            for addr in sorted(self._addrs):
                out.append((host, addr))
        return out

    def _assert_result(
        self,
        want_fn: Callable[[str, str], object],
        got_fn: Callable[[str, str], object],
        host_addr_pairs: List[Tuple[str, str]],
    ) -> None:
        expected = [want_fn(host, addr) for host, addr in host_addr_pairs]
        logging.debug("Running %d checks", len(host_addr_pairs))
        with ThreadPoolExecutor() as e:
            results = e.map(got_fn, *zip(*host_addr_pairs))
        incorrect = []
        for pair, want, got in zip(host_addr_pairs, expected, results):
            if want != got:
                host, addr = pair
                incorrect.append((host, addr, want, got))
        if incorrect:
            lines = [
                f"{got_fn.__name__} gave the wrong result for the following host/addr "
                "combinations:"
            ]
            for host, addr, want, got in incorrect:
                lines.append(f"  {host} -> {addr} ({self._addrs[addr]}): want {want}, got {got}")
            pytest.fail("\n".join(lines))

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
            self._host_addr_pairs(sorted(reachable)),
        )

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
            if addr == "external" and result:
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
            lambda host, addr: [
                (self._addrs[hop] if isinstance(hop, str) else hop)
                for hop in (routes[host][addr] + [addr] if addr in routes[host] else [])
            ],
            traceroute,
            self._host_addr_pairs(sorted(routes)),
        )

    @timer
    def assert_ports_open(
        self, ports: Dict[str, Dict[str, Dict[str, Set[int]]]], ranges: List[Tuple[int, int]]
    ) -> None:
        """Check that only the given ports are open for the given host/addr pairs."""
        host_addr_pairs = []
        for host in ports:
            for addr in ports[host]:
                host_addr_pairs.append((host, addr))
        self._assert_result(
            lambda host, addr: ports[host][addr],
            lambda host, addr: self.nmap(  # pylint: disable=no-value-for-parameter
                host, addr, ranges
            ),
            host_addr_pairs,
        )


BASE_REACHABILITY = {
    "internet": ["external", "internet", "router1_wan", "router2_wan", "ubuntu"],
    "router1": [
        "external",
        "internet",
        "router1_lan",
        "router1_wan",
        "router2_wan",
        "pi1",
        "pi1_vpn",
        "ubuntu",
    ],
    "router2": [
        "external",
        "internet",
        "router1_wan",
        "router2_lan",
        "router2_wan",
        "pi2",
        "pi2_vpn",
        "ubuntu",
    ],
    "pi1": [
        "external",
        "internet",
        "router1_lan",
        "router1_wan",
        "router2_wan",
        "pi1",
        "pi1_vpn",
        "ubuntu",
    ],
    "pi2": [
        "external",
        "internet",
        "router1_wan",
        "router2_lan",
        "router2_wan",
        "pi2",
        "pi2_vpn",
        "ubuntu",
    ],
    "ubuntu": ["external", "internet", "router1_wan", "router2_wan", "ubuntu"],
}


class Email:
    _PORT = 1080

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host

    def clear(self) -> None:
        # SSH login emails are sent asynchronously so they don't delay login. So we
        # sleep to allow login emails from previous tests to arrive before clearing.
        time.sleep(5)
        r = requests.delete(f"http://{self._host}:{self._PORT}/api/emails", timeout=60)
        r.raise_for_status()

    def _get(self, only_from: Optional[str] = None) -> List[Any]:
        r = requests.get(f"http://{self._host}:{self._PORT}/api/emails", timeout=60)
        r.raise_for_status()
        got_emails = r.json()
        if only_from:
            got_emails = [
                e
                for e in got_emails
                if e["from"]["value"][0]["address"] == f"notification@{only_from}.testbed"
                or not e["from"]["value"][0]["address"]
            ]
        return cast(List[Any], got_emails)

    @staticmethod
    def _matches(
        expected: Dict[str, Any], email: Dict[str, Any]  # pylint: disable=redefined-outer-name
    ) -> Tuple[bool, str]:
        def fail_msg(field_name: str, want: str, got: str) -> str:
            return (
                f"Email field '{field_name}' doesn't match: want:\n{want}\ngot:\n{got}\n"
                f"full want:\n{str(expected)}\nfull got:\n"
                + json.dumps(email, sort_keys=True, indent=2)
            )

        def check_field(field_name: str, want: str, got: str) -> str:
            if want != got:
                return fail_msg(field_name, want, got)
            return ""

        msg = check_field("to", expected["to"], email["to"]["value"][0]["address"])
        if msg:
            return False, msg

        msg = check_field("from", expected["from"], email["from"]["value"][0]["address"])
        if msg:
            return False, msg

        if re.fullmatch(expected["subject_re"], email["subject"]) is None:
            return False, fail_msg("subject", expected["subject_re"], email["subject"])

        if re.fullmatch(expected["body_re"], email["text"]) is None:
            return False, fail_msg("text", expected["body_re"], email["text"])

        return True, ""

    def assert_emails(self, emails: List[Dict[str, str]], only_from: Optional[str] = None) -> None:
        """Emails must exactly match."""
        got_emails = self._get(only_from)

        if len(got_emails) != len(emails):
            raise ValueError(
                f"Length of want and got differ ({len(emails)} vs {len(got_emails)}); all "
                "emails:\n" + json.dumps(got_emails, sort_keys=True, indent=2)
            )
        for email, expected in zip(  # pylint: disable=redefined-outer-name
            sorted(got_emails, key=lambda e: cast(str, e["subject"])),
            sorted(emails, key=lambda e: e["subject_re"]),
        ):
            matches, msg = self._matches(expected, email)
            if not matches:
                pytest.fail(msg)

    def assert_has_emails(
        self, emails: List[Dict[str, str]], only_from: Optional[str] = None
    ) -> None:
        """Emails must be a subset of what's on the server."""
        got_emails = sorted(self._get(only_from), key=lambda e: cast(str, e["subject"]))

        for expected in sorted(emails, key=lambda e: e["subject_re"]):
            found = False
            for email in got_emails:  # pylint: disable=redefined-outer-name
                if self._matches(expected, email)[0]:
                    found = True
                    break
            if not found:
                pytest.fail(
                    f"Found no email matching:\n{str(expected)}\nfull got:\n"
                    + json.dumps(got_emails, sort_keys=True, indent=2)
                )


class MockServer:
    _PORT = 443
    _CATCH_ALL = {
        "httpRequest": {},
        "httpResponse": {
            "statusCode": 404,
            "body": "Mockserver fallback",
        },
        "priority": -10,
    }

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host
        self._expectations = []  # type: List[str]

    def clear(self) -> None:
        self._expectations = []
        r = requests.put(f"http://{self._host}:{self._PORT}/reset", timeout=60)
        r.raise_for_status()

        # Catch-all expectation
        r = requests.put(
            f"http://{self._host}:{self._PORT}/expectation", json=self._CATCH_ALL, timeout=60
        )
        r.raise_for_status()

    def expect(self, json: Dict[Any, Any]) -> None:  # pylint: disable=redefined-outer-name
        json["times"] = {"remainingTimes": 1}
        r = requests.put(f"http://{self._host}:{self._PORT}/expectation", json=json, timeout=60)
        r.raise_for_status()
        self._expectations.append(r.json()[0]["httpRequest"])

    def assert_called(self, times: int = 1) -> None:
        for request in self._expectations:
            r = requests.put(
                f"http://{self._host}:{self._PORT}/verify",
                json={
                    "httpRequest": request,
                    "times": {
                        "atLeast": times,
                        "atMost": times,
                    },
                },
                timeout=60,
            )
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
        self._backup_path = self._path + ".backup"
        self._backup_file = self._host.file(self._backup_path)

    def __enter__(self) -> File:
        f = self._host.file(self._path)
        self._path_existed = f.exists

        if self._path_existed:
            if self._backup_file.exists:
                raise ValueError(
                    (
                        f"Cannot shadow '{self._path}' because backup file '{self._backup_path}' "
                        "already exists. Fix it manually."
                    )
                )
            with self._host.sudo():
                self._host.check_output(f"cp -p {self._path} {self._backup_path}")
        else:
            with self._host.sudo():
                self._host.check_output(f"touch {self._path}")

        with self._host.sudo():
            f.clear()
        return f

    def __exit__(self, *exc_info: Any) -> None:
        if self._path_existed:
            if self._backup_file.exists:
                with self._host.sudo():
                    self._host.check_output(f"mv {self._backup_path} {self._path}")
        else:
            with self._host.sudo():
                self._host.check_output(f"rm {self._path}")

    @property
    def path(self) -> str:
        return self._path


def _host_shadow_file(self: Host, path: str) -> ShadowFile:
    return ShadowFile(self, path)


Host.shadow_file = _host_shadow_file  # type: ignore


class ShadowDir:
    """Creates an empty dir in place of path; restores path's contents on exit.

    This lets tests modify the dir's content without messing up the original
    content. Shadow does not persist across reboots.
    """

    def __init__(self, host: Host, path: str) -> None:
        super().__init__()
        self._host = host
        self._path = path
        self._tmpdir = None  # type: Optional[str]

    def __enter__(self) -> "ShadowDir":
        with self._host.sudo():
            tmpdir = self._host.check_output("mktemp -d")
            self._host.check_output(f"chown --reference={self._path} {tmpdir}")
            self._host.check_output(f"chmod --reference={self._path} {tmpdir}")
            self._host.check_output(f"getfacl {self._path} | setfacl --set-file=- {tmpdir}")
            self._host.check_output(f"mount --bind {tmpdir} {self._path}")
            self._tmpdir = tmpdir
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._tmpdir:
            with self._host.sudo():
                self._host.check_output(f"umount {self._path}")
                self._host.check_output(f"rm -r {self._tmpdir}")

    @property
    def path(self) -> str:
        return self._path

    def file(self, path: str) -> File:
        return self._host.file(os.path.join(self._path, path))


def _host_shadow_dir(self: Host, path: str) -> ShadowDir:
    return ShadowDir(self, path)


Host.shadow_dir = _host_shadow_dir  # type: ignore


def _host_client_ip(self: Host) -> str:
    return self.check_output('echo "${SSH_CLIENT}"').split()[0]


Host.client_ip = _host_client_ip  # type: ignore


def _host_make_bigfile(self: Host, path: str, mount_point: str) -> None:
    output = self.check_output(f"df --output=size,used {mount_point} | tail -n 1")
    # Sizes in kiB
    size = int(output.split()[0])
    used = int(output.split()[1])
    # Want to get it up to 92% full
    needed = int(0.92 * size) - used
    self.check_output(f"dd if=/dev/zero of={path} bs=1M count={int(needed / 1024)}")


Host.make_bigfile = _host_make_bigfile  # type: ignore


@contextmanager
def _host_disable_login_emails(self: Host) -> Iterator[None]:
    client_ip = self.client_ip()
    with self.shadow_file("/etc/pi-server/ssh/email-on-login-exceptions") as f:
        with self.sudo():
            f.write(f"vagrant:{client_ip}")
        yield


Host.disable_login_emails = _host_disable_login_emails  # type: ignore


@contextmanager
def _host_group_membership(self: Host, user: str, group: str) -> Iterator[None]:
    in_group = group in self.user(user).groups
    try:
        if not in_group:
            with self.sudo():
                self.check_output(f"adduser '{user}' '{group}'")
            yield
    finally:
        if not in_group:
            with self.sudo():
                self.check_output(f"deluser '{user}' '{group}'")


Host.group_membership = _host_group_membership  # type: ignore


class Time:
    def __init__(
        self,
        host: Host,
        time: datetime.time,  # pylint: disable=redefined-outer-name
        date: datetime.date,
    ) -> None:
        super().__init__()
        self._host = host
        self._initial_time = time
        self._initial_date = date
        self._restore_guest_additions = False

    def __enter__(self) -> "Time":
        with self._host.sudo():
            if self._host.service("virtualbox-guest-utils").is_running:
                self._host.check_output("systemctl stop virtualbox-guest-utils")
                self._restore_guest_additions = True
            self._host.check_output("timedatectl set-ntp false")
        self.set_time(self._initial_time, self._initial_date)
        return self

    def set_time(
        self, time: datetime.time, date: datetime.date  # pylint: disable=redefined-outer-name
    ) -> None:
        with self._host.sudo():
            self._host.check_output(f"timedatectl set-time '{date.isoformat()} {time.isoformat()}'")

    def __exit__(self, *exc_info: Any) -> None:
        with self._host.sudo():
            self._host.check_output("timedatectl set-ntp true")
            if self._restore_guest_additions:
                self._host.check_output("systemctl start virtualbox-guest-utils")


def _host_time(
    self: Host,
    time: datetime.time,  # pylint: disable=redefined-outer-name
    date: Optional[datetime.date] = None,
) -> Time:
    if date is None:
        date = datetime.date.today()
    return Time(self, time, date)


Host.time = _host_time  # type: ignore


class CronRunner:
    def __init__(
        self,
        host: Host,
        time: datetime.time,  # pylint: disable=redefined-outer-name
        cmd_to_watch: str,
        disable_sources_list: bool,
        date: datetime.date,
    ) -> None:
        super().__init__()
        self._host = host
        self._time = time
        self._date = date
        self._cmd_to_watch = cmd_to_watch
        self._disable_sources_list = disable_sources_list
        self._sources_list = None  # type: Optional[ShadowFile]
        self._time_control = None  # type: Optional[Time]

    def __enter__(self) -> None:
        with self._host.sudo():
            if self._disable_sources_list:
                self._sources_list = self._host.shadow_file("/etc/apt/sources.list")
                self._sources_list.__enter__()
        # Large change to override cron's daylight-saving-time handling
        self._time_control = self._host.time(datetime.time(hour=9), self._date)
        self._time_control.__enter__()
        time.sleep(90)
        # Wait for it to start
        self._time_control.set_time(self._time, self._date)
        self._host.check_output(
            (
                "timeout 60 bash -c "
                f"\"while ! pgrep -x -f '{self._cmd_to_watch}'; do true; done\"; true"
            )
        )

    def __exit__(self, *exc_info: Any) -> None:
        # Wait for cron to finish
        self._host.check_output(f"while pgrep -x -f '{self._cmd_to_watch}'; do true; done")
        if self._time_control:
            self._time_control.__exit__(None)
        with self._host.sudo():
            if self._sources_list:
                self._sources_list.__exit__(None)
        time.sleep(2)


def _host_run_crons(
    self: Host,
    time: Optional[datetime.time] = None,  # pylint: disable=redefined-outer-name
    cmd_to_watch: str = "/bin/bash /etc/pi-server/cron/cron-runner",
    disable_sources_list: bool = True,
    date: Optional[datetime.date] = None,
) -> CronRunner:
    if time is None:
        time = datetime.time(hour=2, minute=24, second=50)
    if date is None:
        date = datetime.date.today()
    return CronRunner(self, time, cmd_to_watch, disable_sources_list, date)


Host.run_crons = _host_run_crons  # type: ignore


class Lines:
    def __init__(self, s: str, name: Optional[str] = None) -> None:
        super().__init__()
        self._lines = s.split("\n") if s else []
        self._name = name

    def contains(self, pattern: str) -> bool:
        for line in self._lines:
            if re.fullmatch(pattern, line) is not None:
                return True
        return False

    def count(self, pattern: str) -> int:
        i = 0
        for line in self._lines:
            if re.fullmatch(pattern, line) is not None:
                i += 1
        return i

    def __len__(self) -> int:
        return len(self._lines)

    def __bool__(self) -> bool:
        return len(self) != 0

    def __repr__(self) -> str:
        out = "["
        if self._name:
            out += self._name + " "
        out += f"({len(self._lines)} lines)"
        for line in self._lines:
            out += f"\n  [{line}]"
        out += "]"
        return out


class Journal:
    def __init__(self, host: Host) -> None:
        super().__init__()
        self._host = host

    def clear(self) -> None:
        with self._host.sudo():
            self._host.check_output("journalctl --flush")
            self._host.check_output("journalctl --rotate --vacuum-time=1s")

    def entries(self, service: str) -> Lines:
        with self._host.sudo():
            self._host.check_output("journalctl --flush")
            return Lines(self._host.check_output(f"journalctl -o cat -u '{service}'"))


def _host_journal(self: Host) -> Journal:
    return Journal(self)


Host.journal = _host_journal  # type: ignore


class WebDriver(Firefox):
    def click(self, element: Any) -> None:
        self.execute_script("arguments[0].scrollIntoView();", element)  # type: ignore
        # Scrolling takes time, so we can't click immediately
        time.sleep(1)
        element.click()

    def validate_html(self) -> None:
        assert "404" not in self.page_source
        errors = tidy_document(self.page_source, options={"show-warnings": 0})[1]
        assert not errors

    def validate_links(self) -> Set[ParseResult]:
        this_addr = urlparse(self.current_url).hostname

        def elems(tag: str) -> List[Any]:
            e = cast(List[Any], self.find_elements(By.TAG_NAME, tag))
            assert e
            return e

        for e in elems("link"):
            assert urlparse(e.get_attribute("href")).hostname == this_addr

        for e in elems("img"):
            assert urlparse(e.get_attribute("src")).hostname == this_addr

        same = set()
        other = set()
        for e in elems("a"):
            url = urlparse(e.get_attribute("href"))
            if url.hostname == this_addr:
                same.add(url)
            else:
                other.add(url)
        assert same
        return other


class OpenVPN:
    def __init__(
        # pylint: disable=redefined-outer-name
        self,
        hosts: Dict[str, Host],
        vagrant: Vagrant,
    ) -> None:
        super().__init__()
        self._hosts = hosts
        self._vagrant = vagrant

    @contextmanager
    def connect(self, hostname: str, service: str) -> Iterator[None]:
        host = self._hosts[hostname]
        try:
            with host.sudo():
                host.check_output(f"systemctl start '{service}'")
            time.sleep(20)
            yield
        finally:
            with host.sudo():
                host.check_output(f"systemctl stop '{service}'")


def _hostnames() -> List[str]:
    """Returns all host names from the ansible inventory."""
    return sorted(_ANSIBLE_RUNNER.get_hosts())


def _host_type(hostname: str) -> str:
    match = re.fullmatch(r"([^0-9]+)[0-9]*", hostname)
    if match is None:
        raise ValueError(f"Can't find host type for host '{hostname}'")
    return match.group(1)


def host_number(hostname: str) -> str:
    match = re.fullmatch(r"[^0-9]+([0-9]*)", hostname)
    if match is None:
        raise ValueError(f"Can't find host number for host '{hostname}'")
    return match.group(1)


def _hostnames_by_type() -> Dict[str, List[str]]:
    out = {}  # type: Dict[str, List[str]]
    for hostname in _hostnames():
        out.setdefault(_host_type(hostname), []).append(hostname)
    for value in out.values():
        value.sort()
    return out


def corresponding_hostname(hostname: str, host_type: str) -> str:
    num = host_number(hostname)
    if num:
        return host_type + num
    return "internet"


@pytest.fixture(scope="session")
def hosts() -> Dict[str, Host]:
    """Returns all hosts by name from the ansible inventory."""
    return {name: _ANSIBLE_RUNNER.get_host(name, ssh_config="ssh_config") for name in _hostnames()}


@pytest.fixture(scope="session")
def hosts_by_type(
    hosts: Dict[str, Host]  # pylint: disable=redefined-outer-name
) -> Dict[str, List[Tuple[str, Host]]]:
    out = {}  # type: Dict[str, List[Tuple[str, Host]]]
    for host_type, hostnames in _hostnames_by_type().items():
        out[host_type] = [(hostname, hosts[hostname]) for hostname in hostnames]
    return out


def for_hosts(*args: str) -> MarkDecorator:
    if not args:
        raise ValueError("Input to for_hosts must be non-empty")
    return pytest.mark.for_hosts(hosts=args)


def for_host_types(*args: str) -> MarkDecorator:
    hostnames = []
    hostnames_by_type = _hostnames_by_type()
    for host_type in args:
        hostnames += hostnames_by_type[host_type]
    return for_hosts(*hostnames)


@pytest.fixture(scope="session")
def addrs() -> Dict[str, str]:
    """Returns all IP addresses by name."""
    with open("config.json", encoding="utf-8") as f:
        return cast(Dict[str, str], json.load(f)["addrs"])


@pytest.fixture(scope="session")
def masks() -> Dict[str, str]:
    """Returns all net masks by name."""
    with open("config.json", encoding="utf-8") as f:
        return cast(Dict[str, str], json.load(f)["masks"])


@pytest.fixture(scope="session")
def vagrant() -> Vagrant:
    return Vagrant()


@pytest.fixture(scope="session")
def net(
    # pylint: disable=redefined-outer-name
    hosts: Dict[str, Host],
    addrs: Dict[str, str],
    vagrant: Vagrant,
) -> Net:
    return Net(hosts, addrs, vagrant)


@pytest.fixture(scope="session")
def openvpn(
    # pylint: disable=redefined-outer-name
    hosts: Dict[str, Host],
    vagrant: Vagrant,
) -> OpenVPN:
    return OpenVPN(hosts, vagrant)


@pytest.fixture()
def email(addrs: Dict[str, str]) -> Email:  # pylint: disable=redefined-outer-name
    e = Email(addrs["internet"])
    e.clear()
    return e


@pytest.fixture()
def mockserver(addrs: Dict[str, str]) -> MockServer:  # pylint: disable=redefined-outer-name
    m = MockServer(addrs["internet"])
    m.clear()
    return m


@pytest.fixture(scope="function", autouse=True)
@timer
def ensure_vm_state(
    vagrant: Vagrant, request: FixtureRequest  # pylint: disable=redefined-outer-name
) -> None:
    vms_down: Tuple[str, ...] = ()  # pylint: disable=redefined-outer-name
    for mark in request.keywords.get("pytestmark", []):
        if mark.name == "vms_down":
            vms_down = mark.kwargs["vms"]
    if vagrant.set_states(vms_down):
        time.sleep(30)


def pytest_generate_tests(metafunc: Metafunc) -> None:
    marker = metafunc.definition.get_closest_marker("for_hosts")
    if marker:
        metafunc.parametrize("hostname", marker.kwargs["hosts"])

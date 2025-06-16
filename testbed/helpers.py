import datetime
import inspect
import ipaddress
import json
import logging
import os.path
import re
import time as time_lib
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping, Sequence, Set
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar, cast
from urllib.parse import ParseResult, urlparse

import codetiming
import pytest
import requests
import trparse
import vagrant as vagrant_lib
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from testinfra.host import Host
from testinfra.modules.file import File
from tidylib import tidy_document

# ruff: noqa: ANN401

T = TypeVar("T")


class Timer(codetiming.Timer):
    def __init__(self, name: str = "[unnamed timer]") -> None:
        super().__init__(name=name, logger=logging.debug)
        self._args: list[str] = []
        self._retval: object = None
        self._extra_text: list[object] = []

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
        return super().__enter__()

    def __exit__(self, *exc_info: object) -> None:
        self._update_text()
        super().__exit__(*exc_info)

    def __call__(self, *args: Any) -> Any:
        raise NotImplementedError("Do not use 'Timer' as a decorator, use 'timer' instead")


def timer(f: Callable[..., T]) -> Callable[..., T]:
    arg_details = OrderedDict(inspect.signature(f).parameters)
    has_self = "self" in arg_details
    if has_self:
        del arg_details["self"]
    inject = arg_details and next(iter(arg_details.values())).annotation == Timer

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


class Vagrant:
    @timer
    def __init__(self) -> None:
        super().__init__()
        self._v = vagrant_lib.Vagrant()
        # VM operations are slow, so we cache the state. If state is modified externally, run
        # rescan_state to update the cache.
        self._state: dict[str, bool] = {}
        self.rescan_state()

    def rescan_state(self) -> None:
        self._state = {vm.name: vm.state == self._v.RUNNING for vm in self._v.status()}

    def state(self) -> dict[str, bool]:
        return self._state

    def all_vms(self) -> list[str]:
        return sorted(self._state)

    def running_vms(self) -> list[str]:
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
        time_lib.sleep(60)

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
        return f"AddrInNet({self._mask})"


class Net:
    def __init__(
        self,
        hosts: Mapping[str, Host],
        addrs: Mapping[str, str],
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
    def traceroute(self, t: Timer, host: str, addr: str) -> list[str]:
        """Gets the hops from host to addr; empty list means unreachable."""
        result = trparse.loads(
            self._hosts[host].check_output("sudo traceroute -I %s", self._addrs[addr]),
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
                out.append(next(iter(ips)))
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
        self,
        t: Timer,
        host: str,
        addr: str,
        ranges: Sequence[tuple[int, int]],
    ) -> dict[str, set[int]]:
        """Gets the open ports on addr as seen from host."""
        ports = ",".join([f"{a}-{b}" for (a, b) in ranges])
        result = self._hosts[host].check_output(
            f"sudo nmap -p{ports} --open -Pn -oN - -T4 -sU -sS " + self._addrs[addr],
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

    def _host_addr_pairs(self, hosts: Sequence[str]) -> list[tuple[str, str]]:
        running_vms = self._vagrant.running_vms()
        if sorted(hosts) != running_vms:
            raise ValueError(
                f"'hosts' must exactly match the running VMs: got {sorted(hosts)}, want "
                f"{running_vms}. Either the wrong hosts were passed in , or some VMs are in "
                "the wrong state.",
            )

        out: list[tuple[str, str]] = []
        for host in sorted(hosts):
            out.extend((host, addr) for addr in sorted(self._addrs))
        return out

    def _assert_result(
        self,
        want_fn: Callable[[str, str], object],
        got_fn: Callable[[str, str], object],
        host_addr_pairs: Sequence[tuple[str, str]],
    ) -> None:
        expected = [want_fn(host, addr) for host, addr in host_addr_pairs]
        logging.debug("Running %d checks", len(host_addr_pairs))  # noqa: LOG015
        with ThreadPoolExecutor() as e:
            results = e.map(got_fn, *zip(*host_addr_pairs, strict=True))
        incorrect = []
        for pair, want, got in zip(host_addr_pairs, expected, results, strict=True):
            if want != got:
                host, addr = pair
                incorrect.append((host, addr, want, got))
        if incorrect:
            lines = [
                f"{got_fn.__name__} gave the wrong result for the following host/addr "
                "combinations:",
            ]
            for host, addr, want, got in incorrect:
                lines.append(f"  {host} -> {addr} ({self._addrs[addr]}): want {want}, got {got}")
            pytest.fail("\n".join(lines))

    @timer
    def assert_reachability(self, reachable: Mapping[str, Sequence[str]]) -> None:
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
    def assert_routes(self, routes: Mapping[str, Mapping[str, Sequence[object]]]) -> None:
        """Verify routes between all host/addr pairs are as expected.

        Args:
          routes: mapping from host to target addr to intermediate hops (i.e. not including the
          target itself), for all addrs that should be reachable from host. All host/addr pairs
          not listed will be checked for being unreachable.
        """

        def traceroute(host: str, addr: str) -> list[str]:
            result = self.traceroute(host, addr)
            if addr == "external" and result:
                # External is a special case, in that we don't care where the packets go once they
                # leave the testbed.
                new_result = []
                for hop in result:
                    if hop not in self._addrs.values():
                        break
                    new_result.append(hop)
                result = [*new_result, self._addrs[addr]]
            return result

        self._assert_result(
            lambda host, addr: [
                (self._addrs[hop] if isinstance(hop, str) else hop)
                for hop in ([*routes[host][addr], addr] if addr in routes[host] else [])
            ],
            traceroute,
            self._host_addr_pairs(sorted(routes)),
        )

    @timer
    def assert_ports_open(
        self,
        ports: Mapping[str, Mapping[str, Mapping[str, Set[int]]]],
        ranges: Sequence[tuple[int, int]],
    ) -> None:
        """Check that only the given ports are open for the given host/addr pairs."""
        host_addr_pairs: list[tuple[str, str]] = []
        for host in ports:
            host_addr_pairs.extend((host, addr) for addr in ports[host])
        self._assert_result(
            lambda host, addr: ports[host][addr],
            lambda host, addr: self.nmap(host, addr, ranges),
            host_addr_pairs,
        )


class Email:
    _PORT = 1080

    def __init__(self, host: str) -> None:
        super().__init__()
        self._host = host

    def clear(self) -> None:
        # SSH login emails are sent asynchronously so they don't delay login. So we
        # sleep to allow login emails from previous tests to arrive before clearing.
        time_lib.sleep(5)
        r = requests.delete(f"http://{self._host}:{self._PORT}/api/emails", timeout=60)
        r.raise_for_status()

    def _get(self, only_from: str | None = None) -> list[Any]:
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
        return cast("list[Any]", got_emails)

    @staticmethod
    def _matches(
        expected: Mapping[str, Any],
        email: Mapping[str, Any],
    ) -> tuple[bool, str]:
        def fail_msg(field_name: str, want: str, got: str) -> str:
            return (
                f"Email field '{field_name}' doesn't match: want:\n{want}\ngot:\n{got}\n"
                f"full want:\n{expected}\nfull got:\n" + json.dumps(email, sort_keys=True, indent=2)
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

    def assert_emails(
        self,
        emails: Sequence[Mapping[str, str]],
        only_from: str | None = None,
    ) -> None:
        """Emails must exactly match."""
        got_emails = self._get(only_from)

        if len(got_emails) != len(emails):
            raise ValueError(
                f"Length of want and got differ ({len(emails)} vs {len(got_emails)}); all "
                "emails:\n" + json.dumps(got_emails, sort_keys=True, indent=2),
            )
        for email, expected in zip(
            sorted(got_emails, key=lambda e: cast("str", e["subject"])),
            sorted(emails, key=lambda e: e["subject_re"]),
            strict=True,
        ):
            matches, msg = self._matches(expected, email)
            if not matches:
                pytest.fail(msg)

    def assert_has_emails(
        self,
        emails: Sequence[Mapping[str, str]],
        only_from: str | None = None,
    ) -> None:
        """Emails must be a subset of what's on the server."""
        got_emails = sorted(self._get(only_from), key=lambda e: cast("str", e["subject"]))

        for expected in sorted(emails, key=lambda e: e["subject_re"]):
            found = False
            for email in got_emails:
                if self._matches(expected, email)[0]:
                    found = True
                    break
            if not found:
                pytest.fail(
                    f"Found no email matching:\n{expected}\nfull got:\n"
                    + json.dumps(got_emails, sort_keys=True, indent=2),
                )


class MockServer:
    _PORT = 443
    _CATCH_ALL: Mapping[str, Any] = {
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
        self._expectations: list[str] = []

    def clear(self) -> None:
        self._expectations = []
        r = requests.put(f"http://{self._host}:{self._PORT}/reset", timeout=60)
        r.raise_for_status()

        # Catch-all expectation
        r = requests.put(
            f"http://{self._host}:{self._PORT}/expectation",
            json=self._CATCH_ALL,
            timeout=60,
        )
        r.raise_for_status()

    def expect(self, data: Mapping[Any, Any]) -> None:
        d = dict(data)
        d["times"] = {"remainingTimes": 1}
        r = requests.put(f"http://{self._host}:{self._PORT}/expectation", json=d, timeout=60)
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
                    f"Cannot shadow '{self._path}' because backup file '{self._backup_path}' "
                    "already exists. Fix it manually.",
                )
            with self._host.sudo():
                self._host.check_output(f"cp -p {self._path} {self._backup_path}")
        else:
            with self._host.sudo():
                self._host.check_output(f"touch {self._path}")

        with self._host.sudo():
            f.clear()
        return f

    def __exit__(self, *exc_info: object) -> None:
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


class ShadowDir:
    """Creates an empty dir in place of path; restores path's contents on exit.

    This lets tests modify the dir's content without messing up the original
    content. Shadow does not persist across reboots.
    """

    def __init__(self, host: Host, path: str) -> None:
        super().__init__()
        self._host = host
        self._path = path
        self._tmpdir: str | None = None

    def __enter__(self) -> "ShadowDir":
        with self._host.sudo():
            tmpdir = self._host.check_output("mktemp -d")
            self._host.check_output(f"chown --reference={self._path} {tmpdir}")
            self._host.check_output(f"chmod --reference={self._path} {tmpdir}")
            self._host.check_output(f"getfacl {self._path} | setfacl --set-file=- {tmpdir}")
            self._host.check_output(f"mount --bind {tmpdir} {self._path}")
            self._tmpdir = tmpdir
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._tmpdir:
            with self._host.sudo():
                self._host.check_output(f"umount {self._path}")
                self._host.check_output(f"rm -r {self._tmpdir}")

    @property
    def path(self) -> str:
        return self._path

    def file(self, path: str) -> File:
        return self._host.file(os.path.join(self._path, path))


class Time:
    def __init__(
        self,
        host: Host,
        time: datetime.time,
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

    def set_time(self, time: datetime.time, date: datetime.date) -> None:
        with self._host.sudo():
            self._host.check_output(f"timedatectl set-time '{date.isoformat()} {time.isoformat()}'")

    def __exit__(self, *exc_info: object) -> None:
        with self._host.sudo():
            self._host.check_output("timedatectl set-ntp true")
            if self._restore_guest_additions:
                self._host.check_output("systemctl start virtualbox-guest-utils")


class CronRunner:
    def __init__(
        self,
        host: Host,
        time: datetime.time,
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
        self._sources_list: ShadowFile | None = None
        self._time_control: Time | None = None

    def __enter__(self) -> None:
        with self._host.sudo():
            if self._disable_sources_list:
                self._sources_list = self._host.shadow_file("/etc/apt/sources.list")
                self._sources_list.__enter__()
        # Large change to override cron's daylight-saving-time handling
        self._time_control = self._host.time(datetime.time(hour=9), self._date)
        self._time_control.__enter__()
        time_lib.sleep(90)
        # Wait for it to start
        self._time_control.set_time(self._time, self._date)
        self._host.check_output(
            "timeout 60 bash -c "
            f"\"while ! pgrep -x -f '{self._cmd_to_watch}'; do true; done\"; true",
        )

    def __exit__(self, *exc_info: object) -> None:
        # Wait for cron to finish
        self._host.check_output(f"while pgrep -x -f '{self._cmd_to_watch}'; do true; done")
        if self._time_control:
            self._time_control.__exit__(None)
        with self._host.sudo():
            if self._sources_list:
                self._sources_list.__exit__(None)
        time_lib.sleep(2)


class Lines:
    def __init__(self, s: str, name: str | None = None) -> None:
        super().__init__()
        self._lines = s.split("\n") if s else []
        self._name = name

    def contains(self, pattern: str) -> bool:
        return any(re.fullmatch(pattern, line) is not None for line in self._lines)

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


class WebDriver(Firefox):
    def click(self, element: Any) -> None:
        self.execute_script("arguments[0].scrollIntoView();", element)  # type: ignore[no-untyped-call]
        # Scrolling takes time, so we can't click immediately
        time_lib.sleep(1)
        element.click()

    def validate_html(self) -> None:
        assert "404" not in self.page_source
        errors = tidy_document(self.page_source, options={"show-warnings": 0})[1]
        assert not errors

    def validate_links(self) -> set[ParseResult]:
        this_addr = urlparse(self.current_url).hostname

        def elems(tag: str) -> list[Any]:
            e = cast("list[Any]", self.find_elements(By.TAG_NAME, tag))
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
        self,
        hosts: Mapping[str, Host],
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
            time_lib.sleep(20)
            yield
        finally:
            with host.sudo():
                host.check_output(f"systemctl stop '{service}'")

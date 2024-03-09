#!/usr/bin/env python3

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml

ROLE_PREFIX = "pi_server"
BASE_ROLE = "pi_server.base"
BASE_DEPENDENCY_EXEMPTIONS = frozenset({BASE_ROLE, "pi_server.role_helpers"})


class Role:
    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path.resolve()
        self._tasks_dir = self._path / "tasks"
        self._name = self._path.name
        self._tidy_name = self._name.replace(".", "_")
        self._prefix = ".".join(self._name.split(".")[:-1])
        try:
            self._parse_main()
            self._parse_includes()
        except ValueError as e:
            raise ValueError(f"Error loading role {self._name}: {e}") from e

    @property
    def path(self) -> Path:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    @property
    def tidy_name(self) -> str:
        return self._tidy_name

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def private(self) -> bool:
        return self._private

    @property
    def run_once(self) -> bool:
        return self._run_once

    @property
    def args(self) -> list[str]:
        return self._args

    @property
    def host_vars(self) -> list[str]:
        return self._host_vars

    @property
    def export_vars(self) -> list[str]:
        return self._export_vars

    @property
    def includes(self) -> frozenset[str]:
        return self._includes

    def _parse_main(self) -> None:
        tasks = yaml.safe_load((self._tasks_dir / "main.yml").read_text())
        if len(tasks) != 1:
            raise ValueError(
                f"main.yml must include exactly one task, calling define_role; got {len(tasks)}",
            )
        task = tasks[0]

        want_keys = {"name", "ansible.builtin.include_tasks", "vars"}
        if task.keys() != want_keys:
            raise ValueError(f"task in main.yml must have keys {want_keys}; got {task.keys()}")
        want_name = "Define role"
        if task["name"] != want_name:
            raise ValueError(f'task in main.yml must have name {want_name}; got {task["name"]}')
        want_include = "{{ define_role }}"
        if task["ansible.builtin.include_tasks"] != want_include:
            raise ValueError(
                f"task in main.yml must have ansible.builtin.include_tasks {want_include}; "
                f'got {task["ansible.builtin.include_tasks"]}',
            )

        task_vars = task["vars"]
        want_keys = {"_private", "_run_once", "_args", "_host_vars", "_export_vars"}
        if task_vars.keys() != want_keys:
            raise ValueError(f"vars in main.yml must have keys {want_keys}; got {task_vars.keys()}")

        self._private = cast(bool, task_vars["_private"])
        self._run_once = cast(bool, task_vars["_run_once"])
        self._args = cast(list[str], task_vars["_args"])
        self._host_vars = cast(list[str], task_vars["_host_vars"])
        self._export_vars = cast(list[str], task_vars["_export_vars"])

    def _parse_includes(self) -> None:
        includes = set()
        for path in self._tasks_dir.iterdir():
            if path.is_file():
                tasks = yaml.safe_load(path.read_text())
                if tasks:
                    for task in tasks:
                        if "ansible.builtin.include_role" in task:
                            includes.add(task["ansible.builtin.include_role"]["name"])
        self._includes = frozenset(includes)

    def validate(self, all_roles: Mapping[str, "Role"]) -> None:
        for i in sorted(self._includes):
            if i.startswith(ROLE_PREFIX) and i not in all_roles:
                raise ValueError(f"{self._name} depends on nonexistent role {i}")
        if self._must_depend_on_base() and not self._depends_on_base(all_roles):
            raise ValueError(f"{self._name} does not depend on {BASE_ROLE}")

    def _must_depend_on_base(self) -> bool:
        return self._name not in BASE_DEPENDENCY_EXEMPTIONS and "testbed" not in self._name

    def _depends_on_base(self, all_roles: Mapping[str, "Role"]) -> bool:
        for i in sorted(self._includes):
            if not i.startswith(ROLE_PREFIX):
                continue
            if i == BASE_ROLE:
                return True
            if all_roles[i]._depends_on_base(all_roles):  # noqa: SLF001
                return True
        return False

    def __repr__(self) -> str:
        out = (
            f"{self._name}\n  {self._tidy_name}\n  {self._path}\n"
            f"  Private: {self._private}\n  Run once: {self._run_once}\n"
        )

        out += "  Args:\n"
        for a in sorted(self._args):
            out += f"    {a}\n"

        out += "  Host vars:\n"
        for h in sorted(self._host_vars):
            out += f"    {h}\n"

        out += "  Export vars:\n"
        for e in sorted(self._export_vars):
            out += f"    {e}\n"

        out += "  Includes:\n"
        for i in sorted(self._includes):
            out += f"    {i}\n"
        return out


def load_roles(roots: Sequence[str]) -> dict[str, Role]:
    out: dict[str, Role] = {}
    tidy_names: dict[str, Role] = {}
    for root in roots:
        for path in Path(root).resolve().iterdir():
            if path.is_dir() and (path / "tasks" / "main.yml").exists():
                r = Role(path)
                if r.name in out:
                    raise ValueError(
                        "Found duplicate role names at paths " + f"{r.path} and {out[r.name].path}",
                    )
                if r.tidy_name in tidy_names:
                    raise ValueError(
                        "Found duplicate role tidy names at paths "
                        f"{r.path} and {tidy_names[r.tidy_name].path}",
                    )
                out[r.name] = r
    return out


def dependency_graph(roles: Mapping[str, Role]) -> None:
    prefix_groups: dict[str, set[str]] = {}
    processed = set()
    for r in roles.values():
        if r.prefix in roles:
            if r.prefix not in prefix_groups:
                prefix_groups[r.prefix] = set()
            prefix_groups[r.prefix].add(r.name)
            processed.add(r.name)
    for r in roles.values():
        if r.name not in processed and r.name in prefix_groups:
            prefix_groups[r.name].add(r.name)
            processed.add(r.name)
    for r in roles.values():
        if r.name not in processed:
            if r.prefix not in prefix_groups:
                prefix_groups[r.prefix] = set()
            prefix_groups[r.prefix].add(r.name)
            processed.add(r.name)

    clusters: dict[str, tuple[set[str], set[tuple[str, str]]]] = {}
    other_edges = set()
    for name, group in prefix_groups.items():
        edges = set()
        for r_name in group:
            for i in roles[r_name].includes:
                if i in group:
                    edges.add((r_name, i))
                else:
                    other_edges.add((r_name, i))
        clusters[name] = (group, edges)

    out = ["digraph Deps {", "  newrank=true", "  splines=false"]
    for cluster, items in sorted(clusters.items()):
        nodes, edges = items
        out.append(f'  subgraph "cluster_{cluster}" {{')
        out.extend(f'    "{node}"' for node in sorted(nodes))
        out.extend(f'    "{edge[0]}" -> "{edge[1]}" [minlen=2]' for edge in sorted(edges))
        out.append("  }")

    out.extend(f'  "{edge[0]}" -> "{edge[1]}" [minlen=2]' for edge in sorted(other_edges))

    out.append("}")

    print("\n".join(out))


def main() -> None:
    if len(sys.argv) < 3:  # noqa: PLR2004
        raise ValueError("Usage: ./roles.py command roots...")

    command = sys.argv[1]
    if command not in {"lint", "deps"}:
        raise ValueError(f"Unknown command {command}")

    roles = load_roles(sys.argv[2:])
    for r in roles.values():
        r.validate(roles)

    if command == "lint":
        # Loading and validating is all we have to do here
        pass
    elif command == "deps":
        dependency_graph(roles)


if __name__ == "__main__":
    main()

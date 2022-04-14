# Role helpers

Adds features to `include_role`.

## Usage

1. Include `role_helpers` in your playbook before including any roles that
   depend on it:

    ```yaml
    - include_role:
        name: pi_server.role_helpers
    ```

2. When defining a new role, put the following in `tasks/main.yml` (see 'Vars'
   below for values the vars can take):

    ```yaml
    - name: define role
      include_tasks: "{{ define_role }}"
      vars:
        _private: False
        _run_once: False
        _args: []
        _host_vars: []
        _export_vars: []
    ```

3. Put your actual tasks in `tasks/tasks.yml`.

## Vars

The following vars must be set in the role definition (it's important to set
all of them, so they don't inherit incorrect values from the callers'
definitions):

- `_private`: boolean. If true, the role may only be called from other roles
  whose prefix (everything before the last '.' in the role name) is the same as
  this role's prefix, or whose name is the same as this role's prefix. Trying
  to call a private role from any other role will cause execution to fail.

- `_run_once`: boolean. If true, the role may only be run once per playbook;
  subsequent attempts will be skipped. Typically roles with `_run_once: True`
  won't use args.

- `_args`: list of strings. Names of args required by this role; vars with the
  corresponding names must be set in `include_role` when calling this role,
  otherwise execution will fail. Args are available to `tasks/tasks.yml` in the
  dictionary `args`. E.g. the arg 'foo' would be set as `foo: value` in vars of
  `include_role`, and is available inside the role as `args.foo`.

- `_host_vars`: host vars required by the role. If any aren't found, execution
  will fail.

- `_export_vars`: vars defined inside the role (typically in
  `defaults/main.yml`) which will be available to other roles after this role
  has finished. All other vars in `defaults` are private to the role.

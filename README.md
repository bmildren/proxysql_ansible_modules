# proxysql_ansible_modules

I'll make a pull request against ansible-modules-extras, however in the meantime you can copy the modules to a `./library` dir colocated with your playbook (or any other dir defined using the ansible library config option)

I've produced a basic example below of how the modules can be used based on the "Mini HOW TO on ProxySQL Configuration" in the proxysql docs.  The example supplies the default admin:admin creds, however a config file containing the username and password can also be used.

```
---
- name: proxysql | config | add server
  proxysql_backend_servers:
    login_user: "admin"
    login_password: "admin"
    hostgroup_id: 1
    hostname: "127.0.0.1"
    port: "{{ item }}"
    load_to_runtime: False
    state: present
  register: new_servers
  with_items:
    - 21891
    - 21892
    - 21893

- name: proxysql | config | manage monitor user
  proxysql_global_variables:
    login_user: "admin"
    login_password: "admin"
    variable: "mysql-monitor_username"
    value: "monitor"

- name: proxysql | config | manage monitor user password
  proxysql_global_variables:
    login_user: "admin"
    login_password: "admin"
    variable: "mysql-monitor_password"
    value: "monitor"

- name: proxysql | config | update monitor global variables
  proxysql_global_variables:
    login_user: "admin"
    login_password: "admin"
    variable: "{{ item }}"
    value: 2000
  with_items:
    - "mysql-monitor_connect_interval"
    - "mysql-monitor_ping_interval"
    - "mysql-monitor_read_only_interval"

- name: proxysql | config | load servers to runtime
  proxysql_manage_config:
    login_user: "admin"
    login_password: "admin"
    action: LOAD
    config_settings: "MYSQL SERVERS"
    direction: TO
    config_layer: RUNTIME
  when: new_servers.changed

- name: proxysql | config | add replication hostgroups
  proxysql_replication_hostgroups:
    login_user: "admin"
    login_password: "admin"
    writer_hostgroup: 1
    reader_hostgroup: 2
    state: present

- name: proxysql | config | add users
  proxysql_mysql_users:
    login_user: "admin"
    login_password: "admin"
    username: "{{ item.usr }}"
    password: "{{ item.pwd }}"
    default_hostgroup: 1
    state: present
  with_items:
   - { usr: "root", pwd: "" }
   - { usr: "msandbox", pwd: "msandbox" }

- name: proxysql | config | manage rules
  proxysql_query_rules:
    login_user: "admin"
    login_password: "admin"
    rule_id: 10
    active: True
    username: 'msandbox'
    match_digest: '^SELECT c FROM sbtest1 WHERE id=\?$'
    destination_hostgroup: 2
    cache_ttl: 5000
    apply: True
    load_to_runtime: False
    state: present
  register: rule1

- name: proxysql | config | manage rules
  proxysql_query_rules:
    login_user: "admin"
    login_password: "admin"
    rule_id: 20
    active: True
    username: 'msandbox'
    match_digest: 'DISTINCT c FROM sbtest1'
    destination_hostgroup: 2
    cache_ttl: 5000
    apply: True
    load_to_runtime: False
    state: present
  register: rule2

- name: proxysql | config | load servers to runtime
  proxysql_manage_config:
    login_user: "admin"
    login_password: "admin"
    action: LOAD
    config_settings: "MYSQL QUERY RULES"
    direction: TO
    config_layer: RUNTIME
  when: rule1.changed or rule2.changed

- name: proxysql | config | manage rules
  proxysql_query_rules:
    login_user: "admin"
    login_password: "admin"
    rule_id: 30
    active: True
    username: 'msandbox'
    match_pattern: 'DISTINCT(.*)ORDER BY c'
    replace_pattern: 'DISTINCT\1'
    apply: True
    state: present

- name: proxysql | config | fix rule
  proxysql_query_rules:
    login_user: "admin"
    login_password: "admin"
    rule_id: 20
    apply: False
    state: present

- name: proxysql | config | manage rules
  proxysql_query_rules:
    login_user: "admin"
    login_password: "admin"
    rule_id: 5
    active: True
    username: 'msandbox'
    match_pattern: '^SELECT (c) FROM sbtest(1) WHERE id=(1|2|3)(...)$'
    replace_pattern: 'SELECT c FROM sbtest2 WHERE id=\3\4'
    apply: True
    state: present
```

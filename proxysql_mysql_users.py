#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: proxysql_mysql_users
version_added: "2.2"
author: "Ben Mildren (@bmildren)"
short_description: Adds or removes mysql users from proxysql admin interface.
description:
   - The M(proxysql_mysql_users) module adds or removes mysql users using the
     proxysql admin interface.
options:
  username:
    description:
      - Name of the user connecting to the mysqld or ProxySQL instance.
    required: True
  password:
    description:
      - Password of the user connecting to the mysqld or ProxySQL instance.
  active:
    description:
      - A user with I(active) set to C(False) will be tracked in the database,
        but will be never loaded in the in-memory data structures.
        If ommitted the proxysql default for I(active) is C(True).
  use_ssl:
    description:
      - If I(use_ssl) is set to C(True), connections by this user will be
        made using SSL connections.
        If ommitted the proxysql default for I(use_ssl) is C(False).
  default_hostgroup:
    description:
      - If there is no matching rule for the queries sent by this user, the
        traffic it generates is sent to the specified hostgroup.
        If ommitted the proxysql default for I(use_ssl) is 0.
  default_schema:
    description:
      - The schema to which the connection should change to by default.
  transaction_persistent:
    description:
      -  If this is set for the user with which the MySQL client is connecting
         to ProxySQL (thus a "frontend" user), transactions started within a
         hostgroup will remain within that hostgroup regardless of any other
         rules.
         If ommitted the proxysql default for I(transaction_persistent) is
         C(False).
  fast_forward:
    description:
      - If I(fast_forward) is set to C(True), I(fast_forward) will bypass the
        query processing layer (rewriting, caching) and pass through the query
        directly as is to the backend server.
        If ommitted the proxysql default for I(fast_forward) is C(False).
  backend:
    description:
      -  If I(backend) is set to C(True), this (username, password) pair is
         used for authenticating to the ProxySQL instance.
    default: True
  frontend:
    description:
      - If I(frontend) is set to C(True), this (username, password) pair is
        used for authenticating to the mysqld servers against any hostgroup.
    default: True
  max_connections:
    description:
      - The maximum number of connections ProxySQL will open to the backend
        for this user.
        If ommitted the proxysql default for I(max_connections) is 10000.
  state:
    description:
      - When C(present) - adds the user, when C(absent) - removes the user.
    choices: [ "present", "absent" ]
    default: present
  save_to_disk:
    description:
      - Save mysql host config to sqlite db on disk to persist the
        configuration.
    default: True
  load_to_runtime:
    description:
      - Dynamically load mysql host config to runtime memory.
    default: True
  login_user:
    description:
      - The username used to authenticate to ProxySQL admin interface
    default: None
  login_password:
    description:
      - The password used to authenticate to ProxySQL admin interface
    default: None
  login_host:
    description:
      - The host used to connect to ProxySQL admin interface
    default: '127.0.0.1'
  login_port:
    description:
      - The port used to connect to ProxySQL admin interface
    default: 6032
  config_file:
    description:
      - Specify a config file from which login_user and login_password are to
        be read
    default: ''
'''

EXAMPLES = '''
---
# This example adds a user, it saves the mysql user config to disk, but
# avoids loading the mysql user config to runtime (this might be because
# several users are being added and the user wants to push the config to
# runtime in a single batch using the M(proxysql_manage_config) module).  It
# uses supplied credentials to connect to the proxysql admin interface.

- proxysql_mysql_users:
    login_user: 'admin'
    login_password: 'admin'
    username: 'productiondba'
    state: present
    load_to_runtime: False

# This example removes a user, saves the mysql user config to disk, and
# dynamically loads the mysql user config to runtime.  It uses credentials
# in a supplied config file to connect to the proxysql admin interface.

- proxysql_mysql_users:
    config_file: '~/proxysql.cnf'
    username: 'mysqlboy'
    state: absent
'''

RETURN = '''
stdout:
    description: The mysql user modified or removed from proxysql
    returned: On create/update will return the newly modified user, on delete
              it will return the deleted record.
    type: dict
    sample": {
        "changed": true,
        "msg": "Added user to mysql_users",
        "state": "present",
        "user": {
            "active": "1",
            "backend": "1",
            "default_hostgroup": "1",
            "default_schema": null,
            "fast_forward": "0",
            "frontend": "1",
            "max_connections": "10000",
            "password": "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER",
            "schema_locked": "0",
            "transaction_persistent": "0",
            "use_ssl": "0",
            "username": "guest_ro"
        },
        "username": "guest_ro"
    }
'''

import sys

try:
    import MySQLdb
    import MySQLdb.cursors
except ImportError:
    mysqldb_found = False
else:
    mysqldb_found = True

# ===========================================
# proxysql module specific support methods.
#


def perform_checks(module):
    if module.params["login_port"] < 0 \
       or module.params["login_port"] > 65535:
        module.fail_json(
            msg="login_port must be a valid unix port number (0-65535)"
        )

    if not mysqldb_found:
        module.fail_json(
            msg="the python mysqldb module is required"
        )


def save_config_to_disk(cursor):
    cursor.execute("SAVE MYSQL USERS TO DISK")
    return True


def load_config_to_runtime(cursor):
    cursor.execute("LOAD MYSQL USERS TO RUNTIME")
    return True


class ProxySQLUser(object):

    def __init__(self, module):
        self.state = module.params["state"]
        self.save_to_disk = module.params["save_to_disk"]
        self.load_to_runtime = module.params["load_to_runtime"]

        self.username = module.params["username"]
        self.backend = module.params["backend"]
        self.frontend = module.params["frontend"]

        config_data_keys = ["password",
                            "active",
                            "use_ssl",
                            "default_hostgroup",
                            "default_schema",
                            "transaction_persistent",
                            "fast_forward",
                            "max_connections"]

        self.config_data = dict((k, module.params[k])
                                for k in (config_data_keys))

    def check_user_config_exists(self, cursor):
        query_string = \
            """SELECT count(*) AS `user_count`
               FROM mysql_users
               WHERE username = %s
                 AND backend = %s
                 AND frontend = %s"""

        query_data = \
            [self.username,
             self.backend,
             self.frontend]

        cursor.execute(query_string, query_data)
        check_count = cursor.fetchone()
        return (int(check_count['user_count']) > 0)

    def check_user_privs(self, cursor):
        query_string = \
            """SELECT count(*) AS `user_count`
               FROM mysql_users
               WHERE username = %s
                 AND backend = %s
                 AND frontend = %s"""

        query_data = \
            [self.username,
             self.backend,
             self.frontend]

        for col, val in self.config_data.iteritems():
            if val is not None:
                query_data.append(val)
                query_string += "\n  AND " + col + " = %s"

        cursor.execute(query_string, query_data)
        check_count = cursor.fetchone()
        return (int(check_count['user_count']) > 0)

    def get_user_config(self, cursor):
        query_string = \
            """SELECT *
               FROM mysql_users
               WHERE username = %s
                 AND backend = %s
                 AND frontend = %s"""

        query_data = \
            [self.username,
             self.backend,
             self.frontend]

        cursor.execute(query_string, query_data)
        user = cursor.fetchone()
        return user

    def create_user_config(self, cursor):
        query_string = \
            """INSERT INTO mysql_users (
               username,
               backend,
               frontend"""

        cols = 3
        query_data = \
            [self.username,
             self.backend,
             self.frontend]

        for col, val in self.config_data.iteritems():
            if val is not None:
                cols += 1
                query_data.append(val)
                query_string += ",\n" + col

        query_string += \
            (")\n" +
             "VALUES (" +
             "%s ," * cols)

        query_string = query_string[:-2]
        query_string += ")"

        cursor.execute(query_string, query_data)
        return True

    def update_user_config(self, cursor):
        query_string = """UPDATE mysql_users"""

        cols = 0
        query_data = []

        for col, val in self.config_data.iteritems():
            if val is not None:
                cols += 1
                query_data.append(val)
                if cols == 1:
                    query_string += "\nSET " + col + "= %s,"
                else:
                    query_string += "\n    " + col + " = %s,"

        query_string = query_string[:-1]
        query_string += ("\nWHERE username = %s\n  AND backend = %s" +
                         "\n  AND frontend = %s")

        query_data.append(self.username)
        query_data.append(self.backend)
        query_data.append(self.frontend)

        cursor.execute(query_string, query_data)
        return True

    def delete_user_config(self, cursor):
        query_string = \
            """DELETE FROM mysql_users
               WHERE username = %s
                 AND backend = %s
                 AND frontend = %s"""

        query_data = \
            [self.username,
             self.backend,
             self.frontend]

        cursor.execute(query_string, query_data)
        return True

    def manage_config(self, cursor, state):
        if state:
            if self.save_to_disk:
                save_config_to_disk(cursor)
            if self.load_to_runtime:
                load_config_to_runtime(cursor)

    def create_user(self, check_mode, result, cursor):
        if not check_mode:
            result['changed'] = \
                self.create_user_config(cursor)
            result['msg'] = "Added user to mysql_users"
            result['user'] = \
                self.get_user_config(cursor)
            self.manage_config(cursor,
                               result['changed'])
        else:
            result['changed'] = True
            result['msg'] = ("User would have been added to" +
                             " mysql_users, however check_mode" +
                             " is enabled.")

    def update_user(self, check_mode, result, cursor):
        if not check_mode:
            result['changed'] = \
                self.update_user_config(cursor)
            result['msg'] = "Updated user in mysql_users"
            result['user'] = \
                self.get_user_config(cursor)
            self.manage_config(cursor,
                               result['changed'])
        else:
            result['changed'] = True
            result['msg'] = ("User would have been updated in" +
                             " mysql_users, however check_mode" +
                             " is enabled.")

    def delete_user(self, check_mode, result, cursor):
        if not check_mode:
            result['user'] = \
                self.get_user_config(cursor)
            result['changed'] = \
                self.delete_user_config(cursor)
            result['msg'] = "Deleted user from mysql_users"
            self.manage_config(cursor,
                               result['changed'])
        else:
            result['changed'] = True
            result['msg'] = ("User would have been deleted from" +
                             " mysql_users, however check_mode is" +
                             " enabled.")

# ===========================================
# Module execution.
#


def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_user=dict(default=None, type='str'),
            login_password=dict(default=None, no_log=True, type='str'),
            login_host=dict(default="127.0.0.1"),
            login_unix_socket=dict(default=None),
            login_port=dict(default=6032, type='int'),
            config_file=dict(default='', type='path'),
            username=dict(required=True, type='str'),
            password=dict(no_log=True, type='str'),
            active=dict(type='bool'),
            use_ssl=dict(type='bool'),
            default_hostgroup=dict(type='int'),
            default_schema=dict(type='str'),
            transaction_persistent=dict(type='bool'),
            fast_forward=dict(type='bool'),
            backend=dict(default=True, type='bool'),
            frontend=dict(default=True, type='bool'),
            max_connections=dict(type='int'),
            state=dict(default='present', choices=['present',
                                                   'absent']),
            save_to_disk=dict(default=True, type='bool'),
            load_to_runtime=dict(default=True, type='bool')
        ),
        supports_check_mode=True
    )

    perform_checks(module)

    login_user = module.params["login_user"]
    login_password = module.params["login_password"]
    config_file = module.params["config_file"]

    cursor = None
    try:
        cursor = mysql_connect(module,
                               login_user,
                               login_password,
                               config_file,
                               cursor_class=MySQLdb.cursors.DictCursor)
    except MySQLdb.Error:
        e = sys.exc_info()[1]
        module.fail_json(
            msg="unable to connect to ProxySQL Admin Module.. %s" % e
        )

    proxysql_user = ProxySQLUser(module)
    result = {}

    result['state'] = proxysql_user.state
    if proxysql_user.username:
        result['username'] = proxysql_user.username

    if proxysql_user.state == "present":
        try:
            if not proxysql_user.check_user_privs(cursor):
                if not proxysql_user.check_user_config_exists(cursor):
                    proxysql_user.create_user(module.check_mode,
                                              result,
                                              cursor)
                else:
                    proxysql_user.update_user(module.check_mode,
                                              result,
                                              cursor)
            else:
                result['changed'] = False
                result['msg'] = ("The user already exists in mysql_users" +
                                 " and doesn't need to be updated.")
                result['user'] = \
                    proxysql_user.get_user_config(cursor)
        except MySQLdb.Error:
            e = sys.exc_info()[1]
            module.fail_json(
                msg="unable to modify user.. %s" % e
            )

    elif proxysql_user.state == "absent":
        try:
            if proxysql_user.check_user_config_exists(cursor):
                proxysql_user.delete_user(module.check_mode,
                                          result,
                                          cursor)
            else:
                result['changed'] = False
                result['msg'] = ("The user is already absent from the" +
                                 " mysql_users memory configuration")
        except MySQLdb.Error:
            e = sys.exc_info()[1]
            module.fail_json(
                msg="unable to remove user.. %s" % e
            )

    module.exit_json(**result)

from ansible.module_utils.basic import *
from ansible.module_utils.mysql import *
if __name__ == '__main__':
    main()

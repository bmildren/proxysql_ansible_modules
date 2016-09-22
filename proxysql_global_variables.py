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
module: proxysql_global_variables
version_added: "2.2"
author: "Ben Mildren (@bmildren)"
short_description: Gets or sets the proxysql global variables.
description:
   - The M(proxysql_global_variables) module gets or sets the proxysql global
     variables.
options:
  variable:
    description:
      - Defines which variable should be returned, or if I(value) is specified
        which variable should be updated.
    required: True
  value:
    description:
      - Defines a value the variable specified using I(variable) should be set
        to.
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
# This example sets the value of a variable, saves the mysql admin variables
# config to disk, and dynamically loads the mysql admin variables config to
# runtime. It uses supplied credentials to connect to the proxysql admin
# interface.

- proxysql_global_variables:
    login_user: 'admin'
    login_password: 'admin'
    variable: 'mysql-max_connections'
    value: 4096

# This example gets the value of a variable.  It uses credentials in a
# supplied config file to connect to the proxysql admin interface.

- proxysql_global_variables:
    config_file: '~/proxysql.cnf'
    variable: 'mysql-default_query_delay'
'''

RETURN = '''
stdout:
    description: Returns the mysql variable supplied with it's associted value.
    returned: Returns the current variable and value, or the newly set value
              for the variable supplied..
    type: dict
    "sample": {
        "changed": false,
        "msg": "The variable is already been set to the supplied value",
        "var": {
            "variable_name": "mysql-poll_timeout",
            "variable_value": "3000"
        }
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


def save_config_to_disk(variable, cursor):
    if variable.startswith("admin"):
        cursor.execute("SAVE ADMIN VARIABLES TO DISK")
    else:
        cursor.execute("SAVE MYSQL VARIABLES TO DISK")
    return True


def load_config_to_runtime(variable, cursor):
    if variable.startswith("admin"):
        cursor.execute("LOAD ADMIN VARIABLES TO RUNTIME")
    else:
        cursor.execute("LOAD MYSQL VARIABLES TO RUNTIME")
    return True


def check_config(variable, value, cursor):
    query_string = \
        """SELECT count(*) AS `variable_count`
           FROM global_variables
           WHERE variable_name = %s and variable_value = %s"""

    query_data = \
        [variable, value]

    cursor.execute(query_string, query_data)
    check_count = cursor.fetchone()
    return (int(check_count['variable_count']) > 0)


def get_config(variable, cursor):

    query_string = \
        """SELECT *
           FROM global_variables
           WHERE variable_name = %s"""

    query_data = \
        [variable, ]

    cursor.execute(query_string, query_data)
    row_count = cursor.rowcount
    resultset = cursor.fetchone()

    if row_count > 0:
        return resultset
    else:
        return False


def set_config(variable, value, cursor):

    query_string = \
        """UPDATE global_variables
           SET variable_value = %s
           WHERE variable_name = %s"""

    query_data = \
        [value, variable]

    cursor.execute(query_string, query_data)
    return True


def manage_config(variable, save_to_disk, load_to_runtime, cursor, state):
    if state:
        if save_to_disk:
            save_config_to_disk(variable, cursor)
        if load_to_runtime:
            load_config_to_runtime(variable, cursor)

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
            config_file=dict(default="", type='path'),
            variable=dict(required=True, type='str'),
            value=dict(),
            save_to_disk=dict(default=True, type='bool'),
            load_to_runtime=dict(default=True, type='bool')
        ),
        supports_check_mode=True
    )

    perform_checks(module)

    login_user = module.params["login_user"]
    login_password = module.params["login_password"]
    config_file = module.params["config_file"]
    variable = module.params["variable"]
    value = module.params["value"]
    save_to_disk = module.params["save_to_disk"]
    load_to_runtime = module.params["load_to_runtime"]

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

    result = {}

    if not value:
        try:
            if get_config(variable, cursor):
                result['changed'] = False
                result['msg'] = \
                    "Returned the variable and it's current value"
                result['var'] = get_config(variable, cursor)
            else:
                module.fail_json(
                    msg="The variable \"%s\" was not found" % variable
                )

        except MySQLdb.Error:
            e = sys.exc_info()[1]
            module.fail_json(
                msg="unable to get config.. %s" % e
            )
    else:
        try:
            if get_config(variable, cursor):
                if not check_config(variable, value, cursor):
                    if not module.check_mode:
                        result['changed'] = set_config(variable, value, cursor)
                        result['msg'] = \
                            "Set the variable to the supplied value"
                        result['var'] = get_config(variable, cursor)
                        manage_config(variable,
                                      save_to_disk,
                                      load_to_runtime,
                                      cursor,
                                      result['changed'])
                    else:
                        result['changed'] = True
                        result['msg'] = ("Variable would have been set to" +
                                         " the supplied value, however" +
                                         " check_mode is enabled.")
                else:
                    result['changed'] = False
                    result['msg'] = ("The variable is already been set to" +
                                     " the supplied value")
                    result['var'] = get_config(variable, cursor)
            else:
                module.fail_json(
                    msg="The variable \"%s\" was not found" % variable
                )

        except MySQLdb.Error:
            e = sys.exc_info()[1]
            module.fail_json(
                msg="unable to set config.. %s" % e
            )

    module.exit_json(**result)

from ansible.module_utils.basic import *
from ansible.module_utils.mysql import *
if __name__ == '__main__':
    main()

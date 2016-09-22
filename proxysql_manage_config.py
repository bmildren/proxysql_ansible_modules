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
module: proxysql_manage_config
version_added: "2.2"
author: "Ben Mildren (@bmildren)"
short_description: Writes the proxysql configuration settings between layers.
description:
   - The M(proxysql_global_variables) module writes the proxysql configuration
     settings between layers.  Currently this module will always report a
     changed state, so should typically be used with WHEN however this will
     change in a future version when the CHECKSUM table commands are available
     for all tables in proxysql.
options:
  action:
    description:
      - The supplied I(action) combines with the supplied I(direction) to
        provide the semantics of how we want to move the I(config_settings)
        between the I(config_layers).
    choices: [ "LOAD", "SAVE" ]
    required: True
  config_settings:
    description:
      - The I(config_settings) specifies which configuration we're writing.
    choices: [ "MYSQL USERS", "MYSQL SERVERS", "MYSQL QUERY RULES",
               "MYSQL VARIABLES", "ADMIN VARIABLES", "SCHEDULER" ]
    required: True
  direction:
    description:
      - FROM - denotes we're reading values FROM the supplied I(config_layer)
        and writing to the next layer
        TO - denotes we're reading from the previous layer and writing TO the
        supplied I(config_layer).
    choices: [ "FROM", "TO" ]
    required: True
  config_layer:
    description:
      - RUNTIME - represents the in-memory data structures of ProxySQL used by
        the threads that are handling the requests.
        MEMORY - (sometime also referred as main) represents the in-memory
        SQLite3 database.
        DISK - represents the on-disk SQLite3 database.
        CONFIG - is the classical config file.  You can only LOAD FROM the
        config file.
    choices: [ "MEMORY", "DISK", "RUNTIME", "CONFIG" ]
    required: True
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
# This example saves the mysql users config from memory to disk. It uses
# supplied credentials to connect to the proxysql admin interface.

- proxysql_global_variables:
    login_user: 'admin'
    login_password: 'admin'
    action: "SAVE"
    config_settings: "MYSQL USERS"
    direction: "FROM"
    config_layer: "MEMORY"

# This example loads the mysql query rules config from memory to to runtime. It
# uses supplied credentials to connect to the proxysql admin interface.

- proxysql_global_variables:
    config_file: '~/proxysql.cnf'
    action: "LOAD"
    config_settings: "MYSQL QUERY RULES"
    direction: "TO"
    config_layer: "RUNTIME"
'''

RETURN = '''
stdout:
    description: Simply reports whether the action reported a change.
    returned: Currently the returned value with always be changed=True.
    type: dict
    "sample": {
        "changed": true
    }
'''

import sys

try:
    import MySQLdb
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

    if module.params["config_layer"] == 'CONFIG' and \
            (module.params["action"] != 'LOAD' or
             module.params["direction"] != 'FROM'):

        if (module.params["action"] != 'LOAD' and
                module.params["direction"] != 'FROM'):
            msg_string = ("Neither the action \"%s\" nor the direction" +
                          " \"%s\" are valid combination with the CONFIG" +
                          " config_layer")
            module.fail_json(msg=msg_string % (module.params["action"],
                                               module.params["direction"]))

        elif module.params["action"] != 'LOAD':
            msg_string = ("The action \"%s\" is not a valid combination" +
                          " with the CONFIG config_layer")
            module.fail_json(msg=msg_string % module.params["action"])

        else:
            msg_string = ("The direction \"%s\" is not a valid combination" +
                          " with the CONFIG config_layer")
            module.fail_json(msg=msg_string % module.params["direction"])

    if not mysqldb_found:
        module.fail_json(
            msg="the python mysqldb module is required"
        )


def manage_config(manage_config_settings, cursor):

    query_string = "%s" % ' '.join(manage_config_settings)

    cursor.execute(query_string)
    return True

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
            action=dict(required=True, choices=['LOAD',
                                                'SAVE']),
            config_settings=dict(requirerd=True, choices=['MYSQL USERS',
                                                          'MYSQL SERVERS',
                                                          'MYSQL QUERY RULES',
                                                          'MYSQL VARIABLES',
                                                          'ADMIN VARIABLES',
                                                          'SCHEDULER']),
            direction=dict(required=True, choices=['FROM',
                                                   'TO']),
            config_layer=dict(requirerd=True, choices=['MEMORY',
                                                       'DISK',
                                                       'RUNTIME',
                                                       'CONFIG'])
        ),
        supports_check_mode=True
    )

    perform_checks(module)

    login_user = module.params["login_user"]
    login_password = module.params["login_password"]
    config_file = module.params["config_file"]
    action = module.params["action"]
    config_settings = module.params["config_settings"]
    direction = module.params["direction"]
    config_layer = module.params["config_layer"]

    cursor = None
    try:
        cursor = mysql_connect(module,
                               login_user,
                               login_password,
                               config_file)
    except MySQLdb.Error:
        e = sys.exc_info()[1]
        module.fail_json(
            msg="unable to connect to ProxySQL Admin Module.. %s" % e
        )

    result = {}

    manage_config_settings = \
        [action, config_settings, direction, config_layer]

    try:
        result['changed'] = manage_config(manage_config_settings,
                                          cursor)
    except MySQLdb.Error:
        e = sys.exc_info()[1]
        module.fail_json(
            msg="unable to manage config.. %s" % e
        )

    module.exit_json(**result)

from ansible.module_utils.basic import *
from ansible.module_utils.mysql import *
if __name__ == '__main__':
    main()

from nornir import InitNornir
from nornir.plugins.tasks.networking import napalm_get
from nornir.plugins.tasks.files import write_file
from nornir.plugins.functions.text import print_result
from getpass import getpass
from tempfile import NamedTemporaryFile
import yaml
import json
from os import unlink


"""Get router information from user input"""
host = input("Hostname of router: ")
hostname = input("IP address of router: ")
username = input(f"Username of {hostname}: ")
password = getpass(f"Password of {hostname}: ")
secret = getpass(f"Enable password of {hostname}: ")

"""
See hosts.yaml examples here:
https://github.com/cldeluna/nornir-config/blob/master/hosts.yaml
"""
router_config = {
    host: {
        "hostname": hostname,
        "username": username,
        "password": password,
        "platform": "ios",
        "port": 22,
        "connection_options": {
            "napalm": {
                "extras": {
                    "optional_args": {
                        "secret": secret,
                        "timeout": 1
                    }
                }
            }
        }
    }
}

"""
As this is a demo, I did not permanently save a hosts.yaml file,
hence I am writing to a temporary file.
delete=False is to maintain the temp file after NamedTemporaryFile is closed.
NamedTemporaryFile is not only write the yaml format into temp file, also to get 
the temp file name, so that InitNornir's inventory can open the host_file.
"""
with NamedTemporaryFile(delete=False) as temp:
    temp.write(yaml.safe_dump(router_config).encode('utf-8'))
    tmp_name = temp.name


"""
On how to capture the result from task, read my post:
https://cyruslab.net/2020/02/15/pythonunderstanding-how-to-capture-the-result-you-need-with-nornir/
"""
with InitNornir(inventory={
    "plugin": "nornir.plugins.inventory.simple.SimpleInventory",
    "options": {
        "host_file": tmp_name
    }
}) as nr:
    """
    Get system information, and write to text file.
    """
    result = nr.run(task=napalm_get,
                    getters=["facts"])
    write_response = nr.run(task=write_file,
                            filename=f"{host}_facts.txt",
                            content=json.dumps(result[host][0].result))

    """
    Get config and save to text file.
    https://github.com/nornir-automation/nornir/blob/develop/nornir/plugins/tasks/networking/napalm_get.py
    """
    get_config_result = nr.run(task=napalm_get, getters=["config"], retrieve="all")

    """
    get_config_result[host][0].result produces a dictionary,
    to get the configuration you need to recursively use these keys:
    config then startup.
    """
    write_config_response = nr.run(task=write_file,
                                   filename=f"{host}.cfg",
                                   content=get_config_result[host][0].result["config"]["startup"])


"""unlink is to delete the temp file."""
unlink(tmp_name)

"""Display the result in stdout"""
print_result(result)
print_result(write_response)
print_result(get_config_result)
print_result(write_config_response)

from getpass import getpass
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_config, netmiko_save_config, netmiko_send_command
from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.files import write_file
from nornir.plugins.tasks.text import template_file
from tempfile import NamedTemporaryFile
from socket import gethostbyname, gaierror
from typing import Dict, Union
from ipaddress import ip_address
import yaml
from os import unlink


def is_resolvable(fqdn: str) -> Union[Dict[str, str], Dict[str, bool]]:
    """
    Check if hostname can be resolved to ip address.
    :param fqdn:
        hostname
    :return:
        dictionary of ip address and whether it is ipv4.
    """
    try:
        return {
            "host": gethostbyname(fqdn),
            "is_ipv4": True
        }
    except gaierror:
        return {
            "host": fqdn,
            "is_ipv4": False
        }


def is_ipv4(ipv4: str = None) -> bool:
    """
    Check if ipv4 is valid
    :param ipv4:
        test string for valid ipv4
    :return:
        True if ipv4, false if not ipv4
    """
    try:
        ip_address(ipv4)
        return True
    except ValueError:
        return False


def write_tmp_file(content: Union[str, bytes]) -> str:
    """
    Write to temp file
    :param content:
        Can be bytes or string, if string the function convert to bytes.
    :return:
        temp file name
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    with NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        return tmp.name


def gen_tmp_host_file() -> Dict[str, str]:
    """
    Get user's input then write information to yaml to temp file.
    :return:
        dictionary of hostname and yaml filename
    """
    host = input("Hostname of router: ")
    is_resolv_response = is_resolvable(host)
    if is_resolv_response["is_ipv4"]:
        hostname = is_resolv_response["host"]
    else:
        hostname = input(f"IPv4 address of {host}: ")
    username = input(f"Username of {host}: ")
    password = getpass(f"Password of {hostname}: ")
    valid_response = False
    user_response = str.lower(input("Is enable password the same as management password? (y/n): "))
    while not valid_response:
        if user_response == "y":
            secret = password
            valid_response = True
        elif user_response == "n":
            secret = getpass(f"Enable password for {hostname}: ")
            valid_response = True
        else:
            user_response = str.lower(input("Is enable password the same as management password? (y/n): "))
            valid_response = False

    # dictionary to convert to host yaml file.
    host_config = {
        host: {
            "hostname": hostname,
            "username": username,
            "password": password,
            "platform": "ios",
            "port": 22,
            "connection_options": {
                "netmiko": {
                    "extras": {
                        "device_type": "cisco_ios",
                        "secret": secret
                    },
                    "napalm": {
                        "extras": {
                            "optional_args": {
                                "secret": secret
                            }
                        }
                    }
                }
            }
        }
    }
    yf = yaml.safe_dump(host_config)
    return {
        "filename": write_tmp_file(yf),
        "host": host
    }


if __name__ == "__main__":
    """Demonstration code here"""
    # Get filename
    tmp_filename = gen_tmp_host_file()
    # create nornir object to run task
    with InitNornir(inventory={
        "plugin": "nornir.plugins.inventory.simple.SimpleInventory",
        "options": {
            "host_file": tmp_filename["filename"]
        }
    }) as nr:
        # configuration payload for router's configuration
        payload = {
            "intf_id": "GigabitEthernet0/1",
            "ip_addr": "192.168.2.1",
            "netmask": "255.255.255.252"
        }
        """
        Below are 5 tasks run by nornir:
        task 1. Get running config.
        task 2. Copy running config to file.
        task 3. Generate configuration template based on payload.
        task 4. Configuration set send to router.
        task 5. Save configuration of router.
        """
        # task 1:
        # See https://github.com/nornir-automation/nornir/blob/master/nornir/plugins/tasks/networking/netmiko_send_command.py
        running_config = nr.run(task=netmiko_send_command, name="Get running config",
                                enable=True,
                                command_string="sh running-config")
        # task 2
        write_response = nr.run(task=write_file, filename=f'{tmp_filename["host"]}.cfg',
                                name="Save running config to file",
                                content=running_config[tmp_filename["host"]][0].result)
        # task 3
        cmd = nr.run(task=template_file, path="./templates/", template="configure_interface.j2",
                     conf=payload)
        # task 4
        config_response = nr.run(task=netmiko_send_config, name="configure router",
                                 config_commands=cmd[tmp_filename["host"]][0].result)
        # task 5
        save_response = nr.run(task=netmiko_save_config, name="saving configuration", cmd="write memory")
        print_result(running_config)
        print_result(write_response)
        print_result(config_response)
        print_result(save_response)
        unlink(tmp_filename["filename"])

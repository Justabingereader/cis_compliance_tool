"""Juniper JunOS config collector via Netmiko."""

from netmiko import ConnectHandler


def collect(host: str, username: str, password: str) -> str:
    device = {
        "device_type": "juniper_junos",
        "host": host,
        "username": username,
        "password": password,
    }
    with ConnectHandler(**device) as conn:
        return conn.send_command("show configuration | display set")

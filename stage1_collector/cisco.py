"""Cisco IOS config collector via Netmiko."""

from netmiko import ConnectHandler


def collect(host: str, username: str, password: str, enable_password: str = "") -> str:
    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "secret": enable_password,
    }
    with ConnectHandler(**device) as conn:
        conn.enable()
        return conn.send_command("show running-config")

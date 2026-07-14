"""Cisco IOS config collector via Netmiko."""

from netmiko import ConnectHandler


def collect(host: str, username: str, password: str) -> str:
    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        # GNS3-emulated platforms (e.g. Cat8kv) respond much slower than real
        # hardware, so fast_cli's aggressive timing causes prompt-detection
        # to fail before the device is actually ready.
        "fast_cli": False,
        "conn_timeout": 20,
        "banner_timeout": 20,
        "auth_timeout": 20,
        "read_timeout_override": 30,
    }
    with ConnectHandler(**device) as conn:
        return conn.send_command("show running-config")

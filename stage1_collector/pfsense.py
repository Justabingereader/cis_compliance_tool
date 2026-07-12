"""pfSense config collector.

pfSense's default SSH session drops into a restricted menu rather than a
shell, so Netmiko's CLI-prompt handling doesn't apply. Instead, this pulls
config.xml directly over SFTP.
"""

import paramiko


def collect(host: str, username: str, password: str) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=username, password=password)
        with client.open_sftp() as sftp, sftp.open("/cf/conf/config.xml") as f:
            return f.read().decode("utf-8")
    finally:
        client.close()

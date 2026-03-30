"""
SSH setup and port forwarding helpers for Incus instances.
"""
from __future__ import annotations
import random
import string
import logging

logger = logging.getLogger("ssh_setup")

# Ports reserved for SSH proxy devices (range to pick from)
SSH_PORT_RANGE = (10000, 19999)


def generate_password(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))


def get_used_ports(client) -> set:
    """Scan all instances for existing proxy device ports."""
    used = set()
    try:
        for inst in client.instances.all():
            for dev in inst.devices.values():
                if dev.get("type") == "proxy":
                    listen = dev.get("listen", "")
                    # format: tcp:0.0.0.0:PORT
                    parts = listen.split(":")
                    if len(parts) == 3:
                        try:
                            used.add(int(parts[2]))
                        except ValueError:
                            pass
    except Exception:
        pass
    return used


def find_free_port(client) -> int:
    used = get_used_ports(client)
    rng = list(range(SSH_PORT_RANGE[0], SSH_PORT_RANGE[1] + 1))
    random.shuffle(rng)
    for port in rng:
        if port not in used:
            return port
    raise RuntimeError("No free ports available in SSH port range")


def setup_ssh(inst, password: str) -> None:
    """Install openssh-server and configure root login inside the instance."""
    commands = [
        # Install openssh-server non-interactively
        ["sh", "-c", "DEBIAN_FRONTEND=noninteractive apt-get update -qq"],
        ["sh", "-c", "DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server -qq"],
        # Set root password
        ["sh", "-c", f"echo 'root:{password}' | chpasswd"],
        # Enable root login and password auth
        ["sh", "-c", "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config"],
        ["sh", "-c", "sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config"],
        # Ensure SSH host keys exist and restart
        ["sh", "-c", "ssh-keygen -A && systemctl restart ssh || service ssh restart"],
    ]
    for cmd in commands:
        result = inst.execute(cmd)
        if result.exit_code != 0 and result.stderr:
            logger.warning("cmd=%s stderr=%s", cmd, result.stderr[:200])


def add_ssh_proxy(inst, host_port: int, instance_ip: str) -> None:
    """Add a proxy device to forward host_port → instance:22."""
    inst.devices["ssh"] = {
        "type": "proxy",
        "listen": f"tcp:0.0.0.0:{host_port}",
        "connect": f"tcp:{instance_ip}:22",
    }
    inst.save(wait=True)

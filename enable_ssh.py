"""
============================================
Enable LAN SSH and set user level to 0
============================================
"""

import sys
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from zyxel_backup_restore import ZyxelBackupTool, get_router_credentials


def set_value(parent, name, value, **attributes):
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name, PARAMETER="configured", **attributes)
    node.text = value


def add_ssh_config(router_ip, username, port):
    config = Path.home() / ".ssh" / "config"
    entry = f"""Host airtel
    HostName {router_ip}
    User {username}
    Port {port}
    HostKeyAlgorithms +ssh-rsa
    PreferredAuthentications password
    PasswordAuthentication yes
    PubkeyAuthentication no
"""
    print(f"\nOptional entry for {config}:\n\n{entry}")
    if input("Add this entry? [Y/n]: ").strip().lower() not in ("", "y", "yes"):
        return False

    existing = config.read_text(encoding="utf-8") if config.exists() else ""
    for line in existing.splitlines():
        fields = line.split()
        if fields and fields[0].lower() == "host" and "airtel" in [field.lower() for field in fields[1:]]:
            print(f"Host airtel already exists in {config}; leaving it unchanged.")
            return True

    config.parent.mkdir(
        mode=0o777 if sys.platform == "win32" else 0o700,
        parents=True,
        exist_ok=True,
    )

    config.write_text(entry + "\nHost *\n" + existing, encoding="utf-8")

    if sys.platform != "win32":
        config.chmod(0o600)

    return True


def main():
    router_ip, username, password = get_router_credentials()
    backup = Path(datetime.now().strftime("backup-%Y%m%d-%H%M%S"))
    backup.mkdir(mode=0o700)
    original_cfg = backup / "config-original.cfg"
    original_xml = backup / "config-original.xml"
    edited_xml = backup / "config-ssh.xml"
    edited_cfg = backup / "config-ssh.cfg"

    tool = ZyxelBackupTool(router_ip)
    if not tool.login(username, password):
        raise SystemExit("Login failed")
    if not tool.download_backup(str(original_cfg)):
        raise SystemExit("Backup failed")
    if not tool.decrypt_backup(str(original_cfg), str(original_xml)):
        raise SystemExit("Decryption failed")

    tree = ET.parse(original_xml)
    root = tree.getroot()
    account = next((entry for entry in root.findall("X_5067F0_Ext/LoginPrivilegeMgmt/*")
                    if entry.findtext("UserName") == username), None)
    remote = root.find("X_5067F0_RemoteMGMT")
    ssh = root.find("X_5067F0_RemoteMGMT/SSH")
    if account is None or ssh is None:
        raise SystemExit("Account or SSH settings not found")

    port = ssh.findtext("Port", "22")
    set_value(account, "UserLevel", "0", TYPE="uint8", MIN="0", MAX="2")
    set_value(remote, "Enable", "1", TYPE="boolean")
    set_value(ssh, "Interface", "LAN", TYPE="string", LENGTH="64")
    set_value(ssh, "Port", port, TYPE="uint32", MIN="0", MAX="4294967295")
    tree.write(edited_xml, encoding="UTF-8", xml_declaration=True, short_empty_elements=False)

    if not tool.encrypt_config(str(edited_xml), str(edited_cfg)):
        raise SystemExit("Encryption failed")
    print(f"Original and edited backups saved in {backup}/")
    print(f"SSH will use port {port} on the LAN.")
    print(f"Applying new config and rebooting router.")

    tool.cookie_jar.clear()
    if not tool.login(username, password):
        raise SystemExit("Login failed")
    if not tool.restore_backup(str(edited_cfg)):
        raise SystemExit("Restore failed")

    print("\nRestore request submitted.")
    config_added = add_ssh_config(router_ip, username, port)
    print("\nAfter the router reboots, connect with:")
    if config_added:
        print("ssh airtel")
    else:
        print(f"ssh -p {port} -o HostKeyAlgorithms=+ssh-rsa -o PreferredAuthentications=password "
              f"-o PasswordAuthentication=yes -o PubkeyAuthentication=no {username}@{router_ip}")
    print("Use the router account password.")


if __name__ == "__main__":
    main()

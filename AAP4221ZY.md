# Unlocking the Airtel AirFiber AAP4221ZY (Zyxel EX3310-T0)

Complete, tested procedure for restoring full administrative access on the
**Airtel AirFiber AAP4221ZY** indoor unit.

> **Warning**
> This procedure rewrites the router configuration and reboots the device.
> Only use it on hardware you own. A bad restore can brick the unit and may
> require a UART recovery. Keep the original encrypted backup somewhere safe.
> Disabling TR-069 removes the ISP's ability to manage or re-provision the
> device, and a factory reset wipes every change made here.

---

## TL;DR

The AAP4221ZY is **not** a GPON ONT like the AOT5221ZY/AOT5222ZY. It is the
indoor unit of Airtel's Fixed Wireless Access (AirFiber) product, manufactured
by Zyxel as the **EX3310-T0**. The scripts in this repository do not work on it
out of the box for three reasons:

1. The configuration backup uses a **different encryption key**.
2. The web UI is **HTTPS-only** (port 80 is closed).
3. There is no SSH, Telnet, or remote-management page until the configuration
   is modified.

The unlock is still a configuration backup/edit/restore, but with the
AAP4221ZY-specific key:

```
eqceIcM3cBmbUnysiUw4uG4aVaPE31mh
```

After the restore and reboot, SSH is available on the LAN and the `admin`
account is a **superadmin** (`UserLevel 0`), which yields a root shell.

---

## Hardware

| Item | Value |
|---|---|
| Market name | Airtel AirFiber **AAP4221ZY** |
| OEM / internal model | **Zyxel EX3310-T0** |
| SoC | MediaTek **MT7981B** (Filogic 820) |
| CPU | 2 × ARM Cortex-A53 @ 1.3 GHz (aarch64) |
| RAM | 512 MB DDR3 (~480 MiB usable) |
| Flash | 512 MB SPI-NAND (Micron, 4 KiB page / 256 KiB block) |
| Wi-Fi | MediaTek MT7976, Wi-Fi 6 (802.11ax) 2×2, 2.4 + 5 GHz |
| Ethernet | Airoha AN8855 GbE switch: 2 × LAN + 1 × WAN |
| PoE | WAN port supplies PoE to the outdoor 5G unit (ODU) |
| UART | 3.3 V, **115200 8N1** (pads inside the case) |
| Vendor firmware | OpenWrt 21.02-SNAPSHOT, kernel 5.4.225 |
| Rootfs | dm-verity read-only squashfs + writable ubifs overlay (~82 MB) |

Partition layout (from `/proc/partitions`, sizes in KiB):

```
mtdblock0  524288   whole NAND
mtdblock1    1024   BL2
mtdblock2     512   u-boot-env
mtdblock3    2048   Factory
mtdblock4    1792   FIP
mtdblock5     256   zloader
mtdblock6  131072   ubi    (first firmware bank)
mtdblock7  131072   ubi2   (second firmware bank)
mtdblock8  223744   zyubi
```

---

## Why the AOT procedure does not apply

| Difference | AOT5221ZY / AOT5222ZY | AAP4221ZY |
|---|---|---|
| Config encryption key | `EwhJaD44DfprDOs7OXx9jzAtLg5PKtD8` | `eqceIcM3cBmbUnysiUw4uG4aVaPE31mh` |
| Web UI | HTTP + HTTPS | **HTTPS only** (80 closed) |
| Remote management page | present | **absent** |
| SSH/Telnet before unlock | disabled but present in UI | **no UI, no daemon** |
| USB / VoIP | model dependent | **no USB port, no voice stack** |
| Platform | GPON ONT | AirFiber IDU (5G FWA) |

`enable_ssh.py` assumes the AOT key and an `http://` base URL, so it fails
against this model. Use the procedure below instead.

---

## Prerequisites

- Wired connection to one of the **LAN** ports (the UI is HTTPS-only and the
  device may be at `192.168.1.1`, which commonly collides with another router).
- `python3`, `openssl`, `curl`.
- An SSH client that still accepts **`ssh-rsa` (SHA-1)**: OpenSSH 10 and
  Dropbear's `dbclient` reject this server's host key. **PuTTY `plink`** works.
- The web UI admin password. On a factory-fresh unit this is the **S/N printed
  on the label**; the first login forces a password change (see Step 1).

### Avoid the `192.168.1.1` collision

If another router already owns `192.168.1.1` on Wi-Fi, force the traffic onto
the wired interface. With NetworkManager:

```bash
nmcli connection add type ethernet ifname eno1 con-name target-eth \
  ipv4.method auto ipv4.never-default yes ipv4.route-metric 900 \
  ipv6.method disabled
nmcli connection up target-eth
```

`never-default yes` keeps Wi-Fi as the default route, so the internet (and any
remote session) survives while the wired link is used for the router.

For interactive SSH, use a small local proxy whose upstream socket is bound to
the wired interface, because `ssh -B` only binds the source address and still
routes via Wi-Fi:

```bash
# tcp_proxy.py <listen_port> <target_host> <target_port> <iface>
sudo python3 tcp_proxy.py 2222 192.168.1.1 22 eno1
plink -ssh -P 2222 -l admin -pw '<web-password>' 127.0.0.1
```

Confirm you are on the right box by comparing the MAC:

```bash
arping -I eno1 -c 2 192.168.1.1     # must match the MAC on the label
```

---

## Step 1 — Log in to the web UI

Open `https://192.168.1.1` and log in with `admin` and the label password
(the S/N). The certificate is self-signed (`CN=Airtel-CPE-0001`).

**First login after a factory reset** presents a *CyberSecurity Setup* page
instead of the normal login. It requires a new password and posts it
RSA-encrypted:

- The page contains a 1024-bit public key in a hidden `PublicKey` field.
- `doPasswdRSAEncryption()` uses **JSEncrypt** → **RSA PKCS#1 v1.5**, output
  **base64**.
- The form posts a single field, `uiViewTools_Password`, to
  `/cgi-bin/login_advance.cgi`.
- Rules: 8–64 characters, new password must differ from the old one.

Minimal Python to complete the wizard:

```python
import base64, re, ssl, urllib.parse, urllib.request
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

ctx = ssl._create_unverified_context()
base = "https://192.168.1.1"
url = base + "/cgi-bin/login_advance.cgi"

page = urllib.request.urlopen(url, context=ctx).read().decode()
pem = re.search(r'name="PublicKey"[^>]*value="([^"]+)"', page).group(1)
key = serialization.load_pem_public_key(pem.encode())
enc = base64.b64encode(key.encrypt(b"Airtel@123", padding.PKCS1v15())).decode()

data = urllib.parse.urlencode({"uiViewTools_Password": enc}).encode()
urllib.request.urlopen(urllib.request.Request(url, data=data), context=ctx).read()
urllib.request.urlopen(base + "/cgi-bin/logout_advance.cgi", context=ctx).read()
```

Normal login hashing (used by every later request) is:

```
LoginPasswordValue = md5(encodeURIComponent(password) + ":" + sid)
```

where `sid` is parsed from `var sid = '...'` in the login page.

> The UI locks for **300 seconds after three failed logins**. The lock is
> temporary; a power cycle also clears it.

---

## Step 2 — Download the configuration backup

From the logged-in session:

```bash
# triggers backup generation
curl -k -b cookies.txt -X POST \
  --data 'configFilter=1' \
  https://192.168.1.1/cgi-bin/backupRestore.cgi

sleep 3

# download the encrypted backup
curl -k -b cookies.txt -o config.cfg https://192.168.1.1/romfile.cfg
```

The file is ~480 KB and starts with the ASCII header `Salted__`.

---

## Step 3 — Decrypt

```bash
openssl aes-256-cbc -md MD5 \
  -k "eqceIcM3cBmbUnysiUw4uG4aVaPE31mh" \
  -d -in config.cfg -out config.xml
```

The result is the TR-069 `InternetGatewayDevice` XML. A correct decryption
starts with `<?xml version="1.0" encoding="UTF-8"?>`.

> Keep `config.cfg`, `config.xml` and the key private. The XML contains the
> admin password **in plaintext** under `LoginPrivilegeMgmt`.

---

## Step 4 — Edit the configuration

### 4.1 Superadmin

In `X_5067F0_Ext/LoginPrivilegeMgmt/i1`:

```xml
<UserLevel PARAMETER="configured" TYPE="uint8" MAX="2" MIN="0">0</UserLevel>
```

`1` (default) → `0`.

### 4.2 SSH on the LAN

In `X_5067F0_RemoteMGMT/SSH`:

```xml
<SSH>
  <Type PARAMETER="configured" TYPE="string" LENGTH="64">all</Type>
  <Interface PARAMETER="configured" TYPE="string" LENGTH="64">LAN</Interface>
  ...
</SSH>
```

`Disable` → `LAN`.

### 4.3 Telnet (optional)

The TELNET block usually has no `Interface` element. Add one:

```xml
<TELNET>
  <Type PARAMETER="configured" TYPE="string" LENGTH="64">all</Type>
  <Interface PARAMETER="configured" TYPE="string" LENGTH="64">LAN</Interface>
  ...
</TELNET>
```

The `telnetd` binary exists in the vendor firmware; it can also simply be
started after unlocking (Step 8).

Apply the edits with your editor of choice. If you script it, assert that each
replacement matched exactly once — a silently missed replacement means a
useless restore cycle.

---

## Step 5 — Re-encrypt and verify

```bash
openssl aes-256-cbc -md MD5 \
  -k "eqceIcM3cBmbUnysiUw4uG4aVaPE31mh" \
  -e -in config.xml -out config-modified.cfg

# round-trip check
openssl aes-256-cbc -md MD5 \
  -k "eqceIcM3cBmbUnysiUw4uG4aVaPE31mh" \
  -d -in config-modified.cfg | cmp - config.xml && echo ROUNDTRIP_OK

head -c 8 config-modified.cfg   # must print: Salted__
```

---

## Step 6 — Upload and restore

The UI does not expose a restore form on this firmware, but the CGI still
accepts a multipart upload. Fields, exactly:

| Field | Value |
|---|---|
| `tools_FW_UploadFile` | the encrypted `config-modified.cfg` |
| `restoreFlag` | `2` |
| `postflag` | `1` |
| `HTML_HEADER_TYPE` | `1` |
| `act` | `1` |

```bash
curl -k -b cookies.txt \
  -F 'tools_FW_UploadFile=@config-modified.cfg;filename=config.cfg' \
  -F 'restoreFlag=2' -F 'postflag=1' \
  -F 'HTML_HEADER_TYPE=1' -F 'act=1' \
  https://192.168.1.1/cgi-bin/backupRestore.cgi
```

The router validates the file, applies it and reboots. It comes back in roughly
**60–120 seconds**. The SSH daemon may need a second short reboot before it
listens; wait until both 443 and 22 are reachable.

---

## Step 7 — Connect

The server is an old **Dropbear** that offers **only `ssh-rsa` (SHA-1)**.

- **OpenSSH 10** fails during key exchange.
- **Dropbear `dbclient`** fails with `No matching algo hostkey`.
- **PuTTY `plink`** works.

```bash
plink -ssh -l admin -pw '<web-password>' 192.168.1.1
```

or, through the interface-bound proxy:

```bash
plink -ssh -P 2222 -l admin -pw '<web-password>' 127.0.0.1
```

You land as **root**:

```
uid=0(admin) gid=0(root) groups=0(root)
Linux OpenWrt 5.4.225 #0 SMP ... aarch64 GNU/Linux
```

The password is the current web UI password (not the S/N if you changed it).

---

## Step 8 — Post-unlock hardening and persistence

The vendor firmware resets several settings on every boot, so apply them at
runtime and re-apply them from `/etc/rc.local` (the overlay is writable).

### 8.1 Full web UI (`X_5067F0_DebugVersionFlag`)

```bash
cat > /tmp/flag.txt <<'EOF'
RDMNAME config;
REQUEST;
SEL InternetGatewayDevice.DeviceInfo;
SET X_5067F0_DebugVersionFlag boolean 1;
SEND;
REQUEST;
SEL InternetGatewayDevice.DeviceInfo;
GET X_5067F0_DebugVersionFlag;
SEND;
EOF

ccctest -f /tmp/flag.txt
```

Expect `SET ... success` and `Value=1`. Without this flag, parts of the UI stay
hidden; with it, the remaining vendor controls are exposed.

### 8.2 Disable Airtel auto-configuration (TR-069)

```bash
cat > /tmp/tr069.txt <<'EOF'
RDMNAME config;
REQUEST;
SEL InternetGatewayDevice.ManagementServer;
SET PeriodicInformEnable boolean 0;
SEND;
REQUEST;
SEL InternetGatewayDevice.ManagementServer;
SET URL string "";
SEND;
EOF

ccctest -f /tmp/tr069.txt
```

The stock configuration points at `http://tms.airtelbroadband.in:8103` with
user `airtelacs`. Clearing the URL and disabling periodic inform stops the ACS
from re-provisioning the device.

### 8.3 Telnet

```bash
/usr/sbin/telnetd -p 23
netstat -ltn | grep :23
```

### 8.4 Persist across reboots

`/etc/rc.local` is writable and runs after init. Add:

```sh
# BEGIN_AIRTEL_UNLOCK
(
  sleep 30
  cat > /tmp/unlock_ccc.txt <<'CCC'
RDMNAME config;
REQUEST;
SEL InternetGatewayDevice.DeviceInfo;
SET X_5067F0_DebugVersionFlag boolean 1;
SEND;
REQUEST;
SEL InternetGatewayDevice.ManagementServer;
SET PeriodicInformEnable boolean 0;
SEND;
REQUEST;
SEL InternetGatewayDevice.ManagementServer;
SET URL string "";
SEND;
CCC
  /usr/bin/ccctest -f /tmp/unlock_ccc.txt
) </dev/null >/tmp/unlock-ui.log 2>&1 &
(
  sleep 35
  /usr/sbin/telnetd -p 23
) </dev/null >/tmp/unlock-telnet.log 2>&1 &
# END_AIRTEL_UNLOCK
```

Notes:

- `ccctest` cannot read `/dev/stdin` at boot (`fopen fail`); write the request
  to a temp file first.
- Start `telnetd` with a delay so `/dev/pts` is ready.
- `sleep 30` also lets the vendor boot process finish resetting the flags.

### 8.5 UART (for recovery or OpenWrt)

```bash
fw_setenv EngDebugFlag 0x01
```

After a reboot the console is live at **115200 8N1**; press Enter for the
`ZHAL>` prompt. `ATGU` twice switches to the MediaTek U-Boot shell (`MT7981>`).

---

## Step 9 — Verify

Over SSH:

```bash
id
uname -a
cat /proc/cpuinfo | grep -m1 'model name'
free -k | head -2
df -k /overlay
ps w | grep -E 'telnetd|dropbear' | grep -v grep
netstat -ltn | grep -E ':22|:23'
ccctest -f /tmp/flag.txt        # DebugVersionFlag = 1
```

Or download the running config again and check the two fields:

```bash
grep -n 'UserLevel' config.xml
grep -A2 '<SSH>' config.xml
```

Expected: `UserLevel ... >0<` and `<Interface ...>LAN</Interface>`.

---

## What this device does **not** have

Do not expect the full AOT feature set:

| Feature | Status |
|---|---|
| GPON / optical port | **Not applicable** — fibre/5G terminates at the outdoor ODU |
| USB hosting | **No external USB port**; only the SoC root hubs |
| Samba / SMB | No `smbd`/`nmbd` in the firmware |
| FTP | No `vsftpd`/`ftp` daemon |
| VoIP / RJ-11 FXS | No SIP/voice binaries in this build |
| Package installs | `opkg` exists, but the configured feeds point at retired `21.02-SNAPSHOT` URLs |

The `opkg` overlay has ~77 MB free, but packages built for this vendor kernel
are not available upstream.

---

## OpenWrt (optional, replaces the vendor firmware)

OpenWrt merged official support for this exact board:

- Commit: `ee2e25f0097ecf4245f36edd9974a619c587fc1b`
- PR: <https://github.com/openwrt/openwrt/pull/22809>
- Target: `mediatek/filogic`, device `airtel_aap4221zy`
- Boot chain: BL2 → U-Boot → Zyxel zloader (requires the `zyfwinfo` UBI volume)
- Install: UART + TFTP initramfs, then `sysupgrade`

Caveats:

- Flashing **removes the Airtel ODU/5G management stack**; the unit becomes a
  plain 2×LAN + Wi-Fi router.
- The support is snapshot-grade; reports mention Wi-Fi WPA issues until the
  regulatory domain (`IN`) and a fixed channel are set.
- Installation requires opening the case and UART access.

If you only need root access, the stock unlock above is lower risk.

---

## Recovery / rollback

- The **original** encrypted backup is untouched in `config.cfg`. Uploading it
  restores the pre-unlock state (it still contains `UserLevel 1` and
  `SSH Disable`).
- A **factory reset** (reset pinhole, ~10 s) restores the label defaults:
  `admin` / S/N, SSID `Airtel_Zerotouch`, Wi-Fi password `Airtel@123`, and
  TR-069 enabled. It also **wipes `/etc/rc.local`** and every overlay change.
- If a bad restore prevents boot, UART is the recovery path (see 8.5).

---

## Security notes

- Change the admin password after unlocking; the config file stores it in
  plaintext.
- Keep SSH/Telnet on **LAN only**. Never expose them to the WAN side.
- Treat `config.cfg` as a secret: the encryption key is static and public, so
  anyone with the file can read every credential in it.
- Disabling TR-069 may violate the ISP's terms of service and stops Airtel from
  fixing line faults remotely.

---

## References

- OpenWrt support PR and stock-root recipe:
  <https://github.com/openwrt/openwrt/pull/22809>
- OpenWrt commit: `ee2e25f0097ecf4245f36edd9974a619c587fc1b`
- Original AOT5221ZY backup/restore research:
  <https://gist.github.com/ankurpandeyvns/0f72eb73f5724f83b9ceebe079162505>

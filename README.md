<a name="readme-top"></a>

# :unlock: Unlock Airtel Router

> [!IMPORTANT]
> These scripts have been tested on the following devices and may not work correctly on other models:
>
> - AOT5221ZY
> - AOT5222ZY
> - PMG5617-R20B
> - AAP4221ZY (AirFiber IDU) — different config key and HTTPS-only UI; use the dedicated guide: [AAP4221ZY.md](AAP4221ZY.md)


Restore disabled and hidden settings in the Airtel router web UI. The scripts enable SSH on your Airtel router, unlock the UI and keep it unlocked after each reboot.

![Preview of the unlocked Airtel router UI](.github/preview.png)

## :hammer_and_wrench: Install the tools

Before running the scripts, make sure Python, OpenSSL, and SSH are installed.

### :penguin: Linux

Ubuntu / Debian:

```bash
sudo apt install python-is-python3 openssl openssh-client
```

Arch Linux:

```bash
sudo pacman -S python openssl openssh
```

### :apple: macOS

```bash
brew install python openssl openssh

echo 'export PATH="$(brew --prefix python)/libexec/bin:$PATH"' >> ~/.zshrc
```

### :computer: Windows (Run PowerShell as Administrator)

```powershell
# python
winget install --id Python.PythonInstallManager --exact
py install default

# openssh
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0

# openssl
winget install ShiningLight.OpenSSL.Light

$oldPath = [Environment]::GetEnvironmentVariable("Path", "User")
$newPath = $oldPath + ";C:\Program Files\OpenSSL-Win64\bin"
[Environment]::SetEnvironmentVariable("Path", $newPath, "User")
```

## :rocket: Run the scripts

> [!WARNING]
> Use at your own risk. These scripts change your router configuration and reboot it. Keep the original backup somewhere safe.

Restart your terminal. Make sure you're connected to your router’s Wi-Fi/LAN.

Clone this repository using:

```
git clone https://github.com/sanidhyy/unlock-airtel-router.git
cd unlock-airtel-router
```

or using `Code → Download ZIP`.

### 1. Enable SSH

```bash
python enable_ssh.py
```

Enter your router IP, username, and password when asked. Use the same login as the router web page. The details are saved in `.env` for later runs.

The script saves a backup in a `backup-...` folder, enables SSH, and reboots the router. It also offers to add an `ssh airtel` shortcut so you don’t have to type the long SSH command each time. You can answer `n` if you don't want it.

Wait for the router to come back online before continuing.

### 2. Unlock the UI

```bash
python unlock_ui.py
```

Enter the router password at the SSH prompt. Refresh the router web page when it finishes.

You only need to do this setup once. After future reboots, give the router ~2–3 minutes for the UI unlock script to run.

Keep `.env` and your backup files private, they contain passwords.

**You're good to go :)**

## :raising_hand: Need Help?

If you run into issues during installation or setup:

- **GitHub Discussions** — [Open a Q&A discussion](https://github.com/sanidhyy/unlock-airtel-router/discussions/new?category=q-a) for setup and troubleshooting help.
- **Email** — [sanidhyyy@gmail.com](mailto:sanidhyyy@gmail.com)
- **Discord** — `@sanidhyy`

For bug reports, include your router model, firmware version, operating system, and steps to reproduce the issue. Remove passwords and personal information from logs or screenshots before sharing.

## :mag: How it works

The firmware contains a setting called `InternetGatewayDevice.DeviceInfo.X_5067F0_DebugVersionFlag`. Enabling it exposes many disabled controls and hidden pages across the web UI.

The web UI uses this flag to decide which additional pages and controls are available:

- **`0`** — keep certain pages and controls hidden or disabled.
- **`1`** — make those pages and controls available in the web UI.

The firmware's HTML templates use zone markers to decide which blocks to send to the browser. For example, `lanSetup.html` contains these two zones (save function shortened):

```html
<!-- #BEGINZONE javascript_Apply_Button_zone -->
function uiSave() { /* Existing form validation and save code... */ }
<!-- #ENDZONE javascript_Apply_Button_zone -->

<!-- #BEGINZONE javascript_Hidden_Apply_Button_zone -->
$("#Apply_ID").hide();
<!-- #ENDZONE javascript_Hidden_Apply_Button_zone -->
```

`ipv6LanSetup.html` uses the same pattern. The zone markers are handled by the router before the page reaches your browser; `#Apply_ID` is the jQuery selector for the button. Simply unhiding it in the browser won't restore the missing `uiSave()` function.

[unlock_ui.py](unlock_ui.py) uses the router's `ccctest` tool over SSH to set the live flag to `1`, then reads it back to confirm.

The firmware resets the flag during boot, which is why changing it in a config backup alone didn't work. The script adds a startup block to `/etc/rc.local` that waits 90 seconds and sets it again after each reboot.

## :raised_hands: Contribute

Bug fixes and script improvements are welcome. Open a pull request with a short explanation of your changes and how you tested them. I'll review it before merging. Please keep discussions and reviews respectful.

## :heart: Credits

- [ankurpandeyvns](https://gist.github.com/ankurpandeyvns/0f72eb73f5724f83b9ceebe079162505) — the original Zyxel backup and restore script.
- [Unlock SSH — r/Airtel](https://www.reddit.com/r/Airtel/comments/1v6c308/unlock_ssh/) — the original guide to enabling SSH.

## :rocket: Follow Me

[![Follow Me](https://img.shields.io/github/followers/sanidhyy?style=social&label=Follow&maxAge=2592000)](https://github.com/sanidhyy "Follow Me")
[![Tweet about this project](https://img.shields.io/twitter/url?style=social&url=https%3A%2F%2Fx.com%2F_sanidhyy)](https://x.com/intent/tweet?text=Check+out+these+scripts+for+unlocking+the+Airtel+router+UI.&url=https%3A%2F%2Fgithub.com%2Fsanidhyy%2Funlock-airtel-router "Tweet about this project")

## :star: Give A Star

If you find these scripts useful, give the repository a star.

## :star2: Star History

<a href="https://star-history.com/#sanidhyy/unlock-airtel-router&Timeline">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=sanidhyy/unlock-airtel-router&type=Timeline&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=sanidhyy/unlock-airtel-router&type=Timeline" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=sanidhyy/unlock-airtel-router&type=Timeline" />
</picture>
</a>

<br />

## :balance_scale: Legal Disclaimer

This project is intended for educational and research use.

Users should:

- Only analyze devices they own or have explicit permission to examine
- Comply with all applicable laws and regulations
- Use this information responsibly and ethically
- Respect manufacturer intellectual property

Unauthorized access to network devices may be illegal in your jurisdiction.

<br />
<p align="right">(<a href="#readme-top">back to top</a>)</p>

# Deploying simpleWorkReporter

This document covers practical ways to run `simpleWorkReporter` as a long-lived
personal service.  The app is a single-user tool, so all approaches here
target a per-user deployment rather than a system-wide install.

The three approaches covered:

| Approach | Best for | Survives logout | Auto-restart |
| --- | --- | --- | --- |
| Linux `systemd --user` service | Linux desktops or servers | With `loginctl enable-linger` | Yes |
| `tmux` / `screen` session | Quick deploys, headless servers, no systemd | Yes (detached session) | No |
| Windows Task Scheduler at logon | Windows desktops | No (runs while logged in) | Optional |

Pick one.  Don't run two at once against the same data directory.

## Preferred Install Location

The recommended checkout path is:

```text
$HOME/src/simpleWorkReporter
```

The example unit file, command snippets, and paths throughout this document
assume that location.  If you put the checkout somewhere else, adjust the paths
accordingly.

Data is kept separately from the checkout, under `$HOME/.simpleWorkReporter`
by default (or wherever `SWR_HOME` points).  This separation matters: you can
`git pull` or even re-clone the checkout without touching the database, config,
or certificates.

## Common Prerequisites

Before any of the deployment options below:

1. Install Python 3.11 or newer.
2. Install `openssl` if you intend to generate a self-signed HTTPS certificate
   through the setup wizard.
3. Have an SMTP server address, port, and credentials (if required) ready.

Then clone and set up the checkout:

```bash
mkdir -p $HOME/src
cd $HOME/src
git clone https://github.com/na-parse/simpleWorkReporter.git
cd simpleWorkReporter

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

./swr setup
```

Verify the service starts cleanly in the foreground before wiring it into a
service manager:

```bash
./swr start
```

Open the browser, log in, add a throwaway entry, then stop the server with
`Ctrl-C`.  This confirms the venv, configuration, and certificate state are
all sane before you hand control to systemd/tmux/Task Scheduler.

## Approach 1 -- Linux `systemd --user` Service

This is the cleanest option on a Linux host.  The service runs as your user,
restarts on failure, and integrates with `journalctl` for logs.

### Install The Unit File

A ready-made unit lives at `deploy/simpleworkreporter.service`.  It assumes the
checkout is at `$HOME/src/simpleWorkReporter` with a `.venv/` inside it.

```bash
mkdir -p ~/.config/systemd/user
cp ~/src/simpleWorkReporter/deploy/simpleworkreporter.service \
   ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now simpleworkreporter.service
```

Check status and logs:

```bash
systemctl --user status simpleworkreporter.service
journalctl --user -u simpleworkreporter.service -f
```

### Keep It Running After Logout

By default, user services stop when you log out of all sessions.  To keep the
service alive across logouts and reboots, enable lingering for your account:

```bash
loginctl enable-linger $USER
```

Lingering requires root (it needs `sudo`) and is a one-time setup per host.

### Restart After Code Updates

```bash
cd ~/src/simpleWorkReporter
git pull
. .venv/bin/activate
python -m pip install -r requirements.txt
systemctl --user restart simpleworkreporter.service
```

### Customizing The Unit

If you run multiple instances or use a non-default data directory, copy the
unit under a new name and add an `Environment=` line:

```ini
[Service]
Environment=SWR_HOME=%h/.simpleWorkReporter-alice
WorkingDirectory=%h/src/simpleWorkReporter-alice
ExecStart=%h/src/simpleWorkReporter-alice/.venv/bin/python %h/src/simpleWorkReporter-alice/swr start
```

Each instance needs its own unit file (`simpleworkreporter-alice.service`),
its own data directory, and a distinct service port.

## Approach 2 -- `tmux` or `screen` Session

When systemd isn't available -- old distros, shared shells, restricted
hosts -- a detached terminal multiplexer session is a reasonable fallback.
It survives SSH disconnects but does not auto-restart on crash and does not
survive a reboot.

### Start In A Detached `tmux` Session

```bash
cd ~/src/simpleWorkReporter
tmux new -d -s swr \
  '. .venv/bin/activate && ./swr start 2>&1 | tee -a ~/.simpleWorkReporter/server.log'
```

What this does:

- `tmux new -d -s swr` creates a detached session named `swr`.
- The activate-and-start pipeline runs inside that session.
- `2>&1` merges stderr into stdout so both end up in the log.
- `tee -a ~/.simpleWorkReporter/server.log` writes to a log file _and_ keeps
  output visible if you reattach.

Reattach to watch live output:

```bash
tmux attach -t swr
```

Detach again with `Ctrl-b d`.  Stop the service from inside the session with
`Ctrl-C`, then exit the shell to end the session.

### `screen` Equivalent

```bash
cd ~/src/simpleWorkReporter
screen -dmS swr bash -c \
  '. .venv/bin/activate && ./swr start 2>&1 | tee -a ~/.simpleWorkReporter/server.log'
```

Reattach with `screen -r swr`, detach with `Ctrl-a d`.

### Logging Caveats

`tee -a` appends forever -- there is no built-in rotation.  Options:

- Add a `logrotate` rule for `~/.simpleWorkReporter/server.log` with the
  `copytruncate` directive (the app keeps the file open, so a rename-based
  rotation would lose the handle).
- Periodically truncate the log manually: `: > ~/.simpleWorkReporter/server.log`.
- Drop `tee` entirely and just rely on the tmux scrollback if you don't need
  a persistent log.

### Auto-Start On Boot

If you want the tmux session to come up on reboot without using systemd,
add an `@reboot` cron entry:

```cron
@reboot tmux new -d -s swr 'cd $HOME/src/simpleWorkReporter && . .venv/bin/activate && ./swr start 2>&1 | tee -a $HOME/.simpleWorkReporter/server.log'
```

This still requires the user's cron daemon to run at boot, which on many
modern systems also benefits from `loginctl enable-linger`.  At that point,
the systemd approach is usually simpler -- prefer it if available.

## Approach 3 -- Windows User-Level Setup

`simpleWorkReporter` is a plain Python web app and runs on Windows.  There is
no Windows service template shipped with the project; the deployment options
below are user-level only.

### Recommended Layout

```text
%USERPROFILE%\src\simpleWorkReporter
```

Mirrors the Linux convention.  The data directory defaults to
`%USERPROFILE%\.simpleWorkReporter`.

### Setup In PowerShell

```powershell
mkdir $HOME\src -ErrorAction SilentlyContinue
cd $HOME\src
git clone https://github.com/na-parse/simpleWorkReporter.git
cd simpleWorkReporter

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python .\swr setup
```

Run the server in the foreground first to confirm everything works:

```powershell
python .\swr start
```

### Option A -- Task Scheduler At Logon (Recommended)

A Scheduled Task started at user logon is the closest Windows equivalent to a
`systemd --user` service.  It runs hidden in the background as long as the
user is logged in.

Create a one-line wrapper batch file so the task definition stays simple --
save as `%USERPROFILE%\src\simpleWorkReporter\deploy\swr_start.bat`:

```bat
@echo off
cd /d "%USERPROFILE%\src\simpleWorkReporter"
"%USERPROFILE%\src\simpleWorkReporter\.venv\Scripts\python.exe" swr start >> "%USERPROFILE%\.simpleWorkReporter\server.log" 2>&1
```

Register it with `schtasks`:

```powershell
schtasks /Create /TN "simpleWorkReporter" /SC ONLOGON `
  /TR "%USERPROFILE%\src\simpleWorkReporter\deploy\swr_start.bat" /RL LIMITED
```

To stop, delete, or query the task:

```powershell
schtasks /End    /TN "simpleWorkReporter"
schtasks /Query  /TN "simpleWorkReporter"
schtasks /Delete /TN "simpleWorkReporter" /F
```

Alternatively, open `taskschd.msc` and create the task through the GUI for
finer control (restart on failure, run only when logged on, etc.).

### Option B -- Startup Folder Shortcut

Simpler but more visible: drop a shortcut to `swr_start.bat` into the
user's startup folder.

1. `Win+R`, then `shell:startup` -- opens the per-user Startup folder.
2. Create a shortcut pointing at `deploy\swr_start.bat`.
3. In the shortcut properties, set _Run_ to _Minimized_.

The server will start in a minimized console window on every logon.  Closing
the window stops the service.

### Option C -- WSL2

If you already use WSL2, treat the WSL distribution as a Linux host and use
the `systemd --user` approach above.  This is the most robust Windows option
but requires WSL2 and a distro with systemd enabled (Ubuntu 22.04+ has it on
by default; older distros need `systemd-genie` or `/etc/wsl.conf` tweaks).

The downside: the app only listens while the WSL distro is running.  Browsers
on Windows reach it through `localhost` thanks to WSL2's port forwarding.

### Windows Logging Notes

The `>> server.log 2>&1` redirection in the batch file appends both stdout
and stderr to a single log file.  Like the tmux case, there is no rotation
built in -- prune the file periodically or wrap it in a scheduled cleanup
task.

## Reverse Proxy And HTTPS

The built-in self-signed HTTPS mode is fine for stand-alone use, but if you
already run a reverse proxy on the host -- or you want a real public certificate
from Let's Encrypt -- it is cleaner to terminate TLS at the proxy and let the
app speak plain HTTP on the loopback interface.

Use a reverse proxy when you want:

- A real, browser-trusted TLS certificate (no per-device cert imports).
- Standard ports `80` / `443` rather than a high service port.
- Multiple internal services sharing a single hostname.
- Existing access control, rate limiting, or logging from the proxy layer.

### App-Side Configuration

1. Re-run the setup wizard and choose plain HTTP mode, or use `./swr cert`
   to remove `cert.pem` and `key.pem` from the data directory.  When neither
   file is present, `./swr start` runs HTTP only.
2. Pick a service port that isn't `80` / `443` -- something like `8080` is
   fine.  The proxy will be the only thing talking to it.
3. Restart the service.

> [!IMPORTANT]
> The service binds to `0.0.0.0` by default, so the plain-HTTP port is
> reachable from the LAN.  When running behind a reverse proxy on the same
> host, start the service with `--bind 127.0.0.1` so only the proxy can
> reach it:
>
> ```bash
> ./swr start --bind 127.0.0.1
> ```
>
> Update your `ExecStart=` line (systemd), tmux/screen launch command, or
> Windows wrapper batch file to include the flag.  If the proxy is on a
> different host, leave the default bind and restrict the port at the OS
> firewall instead.

### nginx

A minimal `server` block for `swr.example.com`, assuming a Let's Encrypt
certificate is already provisioned for that hostname:

```nginx
server {
    listen 443 ssl http2;
    server_name swr.example.com;

    ssl_certificate     /etc/letsencrypt/live/swr.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/swr.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name swr.example.com;
    return 301 https://$host$request_uri;
}
```

### Caddy

Caddy handles certificate issuance and renewal automatically -- the entire
config is two lines:

```caddy
swr.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

### Apache

For an existing Apache deployment, enable `mod_proxy`, `mod_proxy_http`, and
`mod_ssl`, then add a virtual host:

```apache
<VirtualHost *:443>
    ServerName swr.example.com

    SSLEngine on
    SSLCertificateFile    /etc/letsencrypt/live/swr.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/swr.example.com/privkey.pem

    ProxyPreserveHost On
    ProxyPass        / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/

    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

### Subpath Hosting

The app assumes it is mounted at the site root (`/`).  Serving it at a subpath
like `/swr/` is not currently supported -- give it its own hostname or a
dedicated port instead.

### Forwarded-Header Caveat

The app does not currently consume `X-Forwarded-For` or `X-Forwarded-Proto`,
so logged client IPs will be the proxy's address and the app's internal
URL-building treats requests as HTTP.  For browser-facing links this is fine
because the proxy rewrites the scheme on the way back out; it only matters if
you start parsing access logs and want the real client IP -- in which case
read it from the proxy's own logs.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `ModuleNotFoundError` on startup | Venv not activated, or `pip install -r requirements.txt` skipped after a `git pull`. |
| Service stops on logout (Linux) | `loginctl enable-linger $USER` not run. |
| Port already in use | Another instance is running, or the previous foreground process didn't exit cleanly. |
| HTTPS works locally but browser warns | Self-signed certificate -- expected.  Import the cert into the browser/OS trust store or front the app with a reverse proxy. |
| `./swr send` output noisy under cron | Normal status goes to stdout; redirect with `>/dev/null` so the scheduler only mails on stderr. |

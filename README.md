# simpleWorkReporter

simpleWorkReporter is a simple web-app designed to streamline the regular _work summary_ email your manager asks you to send.  Yes, you're already tracking your work in the ticket system, your code check-ins are easily auditable, and they could just duck into your team stand-ups every now and again, but here we are.

Add short work entries during the day, review the pending list, and send it off as a formatted SMTP report.  Sent entries stay in history.  It is a single-user, self-hosted tool -- not a team tracker.

## Quick Start

Clone the repo, set up a virtualenv, run the setup wizard, and start the server.

```bash
git clone https://github.com/na-parse/simpleWorkReporter.git
cd ./simpleWorkReporter

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

./setup_server
./start_server
```

The setup wizard walks through worker/manager identity, SMTP settings, service port, an optional access passphrase, and HTTP vs HTTPS mode.  Once running, point a browser at the configured port and start adding tasks.

![simpleWorkReporter pending tasks view](./assets/simpleWorkReporter_PendingTasks.jpg)

> [!NOTE]
> Detailed deployment notes -- system dependencies, running behind a reverse proxy, systemd, multi-instance layouts -- will live in `./deploy/DEPLOYING.md`.

## Sending the Report

Reports can be sent two ways:

- **From the web app** -- the _Send Report_ button in the header opens a preview of the pending entries and current SMTP settings.  Confirming on that page sends the mail; visiting the URL alone does not.  On success, the included entries are marked sent and the dashboard returns to an empty pending list.  On failure, entries stay pending and the SMTP error is shown.
- **From the CLI** -- `./send_report` sends the current pending report headlessly, with no confirmation prompt.  This is intended for cron or another scheduler.  When stdout isn't a TTY routine output is suppressed; errors go to stderr so schedulers don't generate noise on a clean run.

```bash
SWR_HOME=/path/to/data /path/to/checkout/send_report
```

## HTTP vs HTTPS

The service binds to `0.0.0.0` on the configured port by default, so it is reachable from the LAN.  Pass `--bind 127.0.0.1` (or `-b 127.0.0.1`) to `./start_server` to restrict it to loopback -- useful when fronting the app with a reverse proxy on the same host.

It runs in one of two modes:

- **Self-signed HTTPS** for stand-alone operation.  Setup can generate `cert.pem` and `key.pem` in the data directory.  When both exist, `./start_server` runs HTTPS only.
- **Plain HTTP** for local-only use or when nginx, Apache, Caddy, or another reverse proxy terminates HTTPS in front of the app.  Startup prints a warning in this mode.

Re-running `./setup_server` shows the current certificate state and offers a menu to add, replace, or remove the cert files.

## SMTP

Reports are sent from the worker address to the manager address (worker is copied).  Three SMTP modes are supported:

- **STARTTLS** with authentication -- normally port `587`.
- **Implicit TLS / SMTPS** with authentication -- normally port `465`.
- **Plain SMTP** without authentication -- normally port `25`.

Authenticated plain SMTP and unauthenticated TLS SMTP are intentionally not supported.  The stored SMTP password is never shown in the UI; leave the replacement field blank on the config page to keep the existing value.

## Tools

A handful of helper scripts ship alongside the main server commands.  These are for developers and one-off maintenance -- they aren't part of normal day-to-day use.

| Script | Purpose |
| --- | --- |
| `./setup_server` | Interactive setup wizard. |
| `./start_server` | Start the local web service. |
| `./send_report` | Send the pending report headlessly (for cron). |
| `./cert_tool` | Manage the self-signed HTTPS certificate. |
| `./db_tool` | Initialize, migrate, or seed the SQLite database. |

`./db_tool demo` will load varied fixture entries for visual testing.  Add `--clear` to wipe existing tasks first, and `-y` for non-interactive use.  Don't point it at a real working database.

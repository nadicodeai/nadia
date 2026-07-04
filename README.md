# Nadia Agent

Nadia Agent is an installed AI agent that works alongside the people in your
company, taking on jobs they hand it. Those jobs come from looking at the
workflows your team already runs and identifying the parts an agent can own,
with clear human approval points.

## ⬇️ Download the app

**[→ Download the latest release](https://github.com/nadicodeai/nadia/releases/latest)**

Grab the installer for your platform from the release assets:

| Platform | File to download |
|----------|------------------|
| **macOS** (Apple Silicon) | `Nadia-Agent-*-mac-arm64.dmg` |
| **Windows** | `Nadia-Agent-*-win-x64.exe` (or `.msi`) |
| **Linux** | `Nadia-Agent-*-linux-x86_64.AppImage`, `.deb`, or `.rpm` |

**macOS:** open the `.dmg` and drag **Nadia** into Applications. The app is
ad-hoc signed, so on first launch right-click it and choose **Open** to get past
Gatekeeper (only needed once).

Prefer the terminal, or setting up a server? See **Install the server & CLI**
below.

## Install the server & CLI

Linux and macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/nadia/main/scripts/install.sh | bash
```

Then run:

```bash
nadia setup
nadia gateway install
nadia gateway start
```

For headless or CI bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/nadia/main/scripts/install.sh | bash -s -- --skip-setup --skip-browser --no-skills
```

## What It Runs

- a command-line Nadia Agent runtime
- a gateway for customer messaging workflows
- a desktop app for macOS, Windows, and Linux
- local configuration under `~/.nadia`
- optional setup for managed model access through the NadicodeAI Portal

Every [GitHub Release](https://github.com/nadicodeai/nadia/releases) publishes
the desktop app installers for macOS, Windows, and Linux alongside the shell
installer and source archive.

## Activation

When managed access is enabled, a Nadia Instance is activated through the Nadia
Agents Portal. The installer shows a short code and URL; an authenticated
operator approves the instance, and Nadia receives an instance credential for
model access and check-ins.

## Ownership

Nadia is designed around customer-owned operational knowledge: workflow steps,
corrections, memory, examples, and operating rules stay with the deployed
instance. The customer decides what Nadia may do automatically and where a
person must approve.

## Development

Create a virtual environment and install the package:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
nadia --help
```

## License

MIT.

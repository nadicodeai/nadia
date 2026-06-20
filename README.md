# Nadia Agent

Nadia Agent is an installed AI agent for companies that want one repeated
workflow handled with clear human approval points.

Install Nadia on a Linux or macOS server, pair it with your messaging gateway,
and teach it the steps, rules, examples, exceptions, and permission boundaries
your team already uses. Nadia handles the repeatable parts while people keep
judgment, relationships, approvals, and responsibility.

## Install

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
- local configuration under `~/.nadia`
- optional setup for managed model access through the Nadia Agents Portal

This public source tree ships the server, CLI, and gateway runtime. Desktop,
website, bundled skill packs, optional integration catalogs, and Windows/macOS
desktop installer sources are included as branded Nadia product surfaces.

GitHub Releases publish the shell installer plus desktop app artifacts for
macOS, Windows, and Linux from this public source tree.

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

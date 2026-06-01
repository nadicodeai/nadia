# Golden VM for Forward-Deployed Argo Engineers

This is the supported VM-oriented path for customer infrastructure. It is not a
Docker deployment path.

## Base OS

Use Ubuntu Server 22.04 LTS as the default golden image. It matches the existing
install smoke baseline in `tests/install_smoke/run.sh`, has stable `apt`
packages for Argo's host dependencies, and is broadly available across customer
hypervisors and cloud VM catalogs.

Ubuntu Server 24.04 LTS is a reasonable later migration target, but 22.04 is the
conservative baseline for the first FDE image because the repo already tests the
customer installer against it.

## What Gets Baked

Run `scripts/golden-vm-bake.sh` on a clean VM before snapshotting. The bake
installs:

- OS packages needed by the full host experience: Git, curl, Python venv/pip,
  FFmpeg, ripgrep, xz-utils, compiler/build headers, OpenSSH client, and basic
  process tools.
- Argo from the supported customer installer URL with `--skip-setup`.
- The FDE optional Python surface that the base installer does not install:
  Honcho, Telegram, Edge TTS, and `ddgs`.
- Browser tooling unless `--skip-browser` is passed.
- `/usr/local/bin/argo-customer-init`.
- `~/.argo/SOUL.md.template` and `~/.argo/honcho.json.template`.
- `security.allow_lazy_installs: false` in the base config.

The important policy is not "lazy install everything later." The golden VM does
the opposite for the expected customer-facing surface: install it during the
bake, then disable runtime lazy package installs so a customer deployment does
not unexpectedly reach out to package registries on first use.

## Why Telegram And Honcho Need Explicit Bake Coverage

Argo has Telegram and Honcho support in-tree, but the public installer runs the
upstream-style `uv sync --extra all --locked` flow. In `upstream/pyproject.toml`,
the `all` extra intentionally excludes some runtime feature extras. The matching
runtime mechanism is `upstream/tools/lazy_deps.py`, where:

- `platform.telegram` maps to `python-telegram-bot[webhooks]==22.6`.
- `memory.honcho` maps to `honcho-ai==2.0.1`.

So the golden VM must preinstall those packages. Otherwise the first customer
profile that enables Telegram or Honcho can trigger a runtime package install.

## Bake Command

On the clean VM:

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/main/scripts/golden-vm-bake.sh -o /tmp/golden-vm-bake.sh
curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/main/scripts/argo-customer-init -o /tmp/argo-customer-init
chmod +x /tmp/golden-vm-bake.sh /tmp/argo-customer-init
/tmp/golden-vm-bake.sh
```

For a headless customer image where browser automation is intentionally excluded:

```bash
/tmp/golden-vm-bake.sh --skip-browser
```

For a dry-run plan:

```bash
/tmp/golden-vm-bake.sh --dry-run --skip-argo-install --skip-os-packages --skip-browser
```

## Snapshot Boundary

Snapshot after the bake completes and before any customer-specific profile is
created.

Do not bake these into the snapshot:

- Telegram bot tokens.
- Honcho API keys.
- Provider API keys.
- Customer SOUL content.
- Customer profile directories.
- Gateway pairing state, sessions, or logs.

The bake script removes the common mutable Argo state paths before completion.

## Per-Customer Initialization

After cloning the golden VM into a customer environment, the FDE runs:

```bash
argo-customer-init \
  --profile acme-prod \
  --honcho-workspace acme \
  --honcho-peer fde-01 \
  --honcho-api-key "$HONCHO_API_KEY" \
  --telegram-token "$TELEGRAM_BOT_TOKEN" \
  --telegram-allowed-users "12345678,87654321"
```

This creates `~/.argo/profiles/acme-prod/` and writes:

- `config.yaml` with `memory.provider: honcho`,
  `gateway.platform: telegram`, and `security.allow_lazy_installs: false`.
- `honcho.json` from the baked template and passed customer values.
- `.env` containing Telegram settings, mode `0600`.
- `SOUL.md` from the baked SOUL template.

By default the init command then runs:

```bash
argo -p <profile> gateway install
argo -p <profile> gateway start
```

Use `--skip-gateway` for disposable validation environments that do not run
systemd.

## Validation

On a baked VM, verify:

```bash
argo --version
/tmp/golden-vm-bake.sh --print-python-packages
python -c "import honcho, telegram, edge_tts, ddgs"
```

After customer init:

```bash
argo -p acme-prod doctor
argo -p acme-prod gateway status
```

The result should be a repeatable VM image where forward-deployed engineers only
provide the customer profile name, Honcho values, Telegram values, and customer
SOUL content.

## Maintainer VM Smoke

The real golden-image smoke is:

```bash
make golden-vm-qemu-smoke
```

It runs QEMU/KVM from a disposable Docker runner, boots an Ubuntu 22.04 cloud
image as a real VM, runs the bake inside that VM, shuts it down, creates a
customer clone disk backed by the baked golden disk, boots the clone, and runs
`argo-customer-init` inside the cloned VM.

The lighter `make golden-vm-smoke` target is only a container smoke. It is useful
for fast script checks, but it is not a golden image validation.

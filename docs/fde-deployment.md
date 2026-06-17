# Nadia FDE Customer Deployment

This document is the customer deployment contract for forward deployed
engineers. The three supported modalities are native installer, container, and
VM image. They must converge to the same baseline.

## Shared Baseline

Every modality must provide:

- Nadia installed from the supported `release` installer or from the repo-built
  container/image artifact.
- Honcho preinstalled: `honcho-ai==2.0.1`.
- Telegram preinstalled: `python-telegram-bot[webhooks]==22.6`.
- Edge TTS preinstalled: `edge-tts==7.2.7`.
- Web search dependency preinstalled: `ddgs`.
- `security.allow_lazy_installs: false` in the base config and generated
  customer profile config.
- `nadia-customer-init` or the Windows `nadia-customer-init.ps1` equivalent.
- Customer-specific secrets written only during customer initialization, never
  baked into an image.

The package list comes from `upstream/tools/lazy_deps.py` and
`upstream/pyproject.toml`. Telegram and Honcho are present as feature code, but
their packages are lazy dependency entries, so FDE deployments install them at
provision time instead of at first customer use.

## Native Installer

macOS and Linux use:

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/nadia-fde-provision.sh -o /tmp/nadia-fde-provision.sh
curl -fsSL https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/nadia-customer-init -o /tmp/nadia-customer-init
chmod +x /tmp/nadia-fde-provision.sh /tmp/nadia-customer-init
/tmp/nadia-fde-provision.sh
```

Windows uses:

```powershell
irm https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/nadia-fde-provision.ps1 -OutFile $env:TEMP\nadia-fde-provision.ps1
irm https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/nadia-customer-init.ps1 -OutFile $env:TEMP\nadia-customer-init.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\nadia-fde-provision.ps1
```

Then initialize the customer profile.

Linux/macOS:

```bash
nadia-customer-init \
  --profile acme-prod \
  --honcho-workspace acme \
  --honcho-peer fde-01 \
  --honcho-api-key "$HONCHO_API_KEY" \
  --telegram-token "$TELEGRAM_BOT_TOKEN" \
  --telegram-allowed-users "$TELEGRAM_ALLOWED_USERS"
```

Windows:

```powershell
& "$env:LOCALAPPDATA\nadia\bin\nadia-customer-init.ps1" `
  -Profile acme-prod `
  -HonchoWorkspace acme `
  -HonchoPeer fde-01 `
  -HonchoApiKey $env:HONCHO_API_KEY `
  -TelegramToken $env:TELEGRAM_BOT_TOKEN `
  -TelegramAllowedUsers $env:TELEGRAM_ALLOWED_USERS
```

## Container

Build the FDE image:

```bash
make fde-container
```

The image target is `runtime-fde` and the local tag is:

```text
ghcr.io/nadicodeai/nadia:fde-dev
```

Run profile initialization inside the container with persistent `/opt/data`:

```bash
docker run --rm -it \
  -v nadia-acme:/opt/data \
  --entrypoint /usr/local/bin/nadia-customer-init \
  ghcr.io/nadicodeai/nadia:fde-dev \
  --profile acme-prod \
  --honcho-workspace acme \
  --honcho-peer fde-01 \
  --honcho-api-key "$HONCHO_API_KEY" \
  --telegram-token "$TELEGRAM_BOT_TOKEN" \
  --telegram-allowed-users "$TELEGRAM_ALLOWED_USERS"
```

Start the normal container afterward with the same volume.

## VM Image

The first supported VM artifact is qcow2 on Ubuntu Server 22.04 LTS:

```bash
make fde-vm-image
```

Expected outputs:

```text
dist/images/nadia-fde-ubuntu-22.04.qcow2
dist/images/nadia-fde-ubuntu-22.04.qcow2.sha256
dist/images/nadia-fde-ubuntu-22.04.qcow2.info
dist/images/nadia-fde-ubuntu-22.04.qcow2.build.log
```

The VM build boots a real Ubuntu cloud image under QEMU/KVM, runs the bake,
shuts down, creates a clone backed by the baked disk, boots the clone, and runs
customer initialization in the clone. Docker-only checks are not VM acceptance.

Ubuntu 22.04 is the first baseline because the repo already validates customer
installer behavior on Ubuntu 22.04, while Nadia's installer provisions the Python
runtime itself (`3.11`) through `uv`. Ubuntu 24.04 can be added after the same
QEMU clone acceptance passes there.

## Live Acceptance

Live Telegram/Honcho acceptance requires explicit test credentials:

```bash
export FDE_HONCHO_API_KEY=...
export FDE_HONCHO_WORKSPACE=nadia-fde-live
export FDE_TELEGRAM_BOT_TOKEN=...
export FDE_TELEGRAM_ALLOWED_USERS=...
make fde-live-smoke
```

Without those variables, the live smoke exits `77` and is not accepted as a live
credential test.

## Verification Commands

```bash
pytest tests/test_golden_vm_scripts.py tests/test_fde_deployment_contract.py -q
bash -n scripts/nadia-fde-provision.sh scripts/golden-vm-bake.sh scripts/nadia-customer-init scripts/fde-vm-image.sh tests/fde_container/run.sh tests/fde_live/run.sh
make fde-container-smoke
make golden-vm-qemu-smoke
make fde-vm-image
```

macOS and Windows native acceptance must run on real macOS and Windows runners
or hosts. A Linux shell test is not acceptance for those platforms.

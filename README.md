# Nadia — the NadicodeAI agent

Nadia is NadicodeAI's AI agent for your desktop. Sign in with the
[NadicodeAI Portal](https://portal.nadicode.ai) to get started — your
subscription and models are managed there.

Nadia can connect to the channels you already use: Telegram, WhatsApp,
Signal, iMessage, Email, SMS, Discord, Slack, Microsoft Teams, Google Chat,
Mattermost, Matrix, and Home Assistant, plus webhooks and an API.

Available in English and Italian.

## Install

Download the latest release from the
[Releases page](https://github.com/nadicodeai/nadia/releases).

**macOS (Apple Silicon)** — `.dmg`

Open the `.dmg`, then drag Nadia into Applications.

The first time you open Nadia, macOS asks you to confirm apps downloaded
outside the App Store:

1. Double-click Nadia in Applications. macOS shows a message that it can't
   verify the developer — click **Done**.
2. Open System Settings → Privacy & Security and scroll to Security. You'll
   see a note that Nadia was blocked, with an **Open Anyway** button.
3. Click **Open Anyway**, confirm with your password or Touch ID, then open
   Nadia once more to confirm.

You only need to do this once.

**Linux (x86_64)** — `.AppImage`, `.deb`, or `.rpm`

```
chmod +x Nadia-*.AppImage
./Nadia-*.AppImage
```

Debian and Ubuntu users can install the `.deb`; Fedora and RHEL users can
install the `.rpm`.

**Windows** — Windows support is coming soon.

## First launch

The first launch takes a couple of minutes to finish setting up and needs an
internet connection. Nadia then asks you to sign in with the NadicodeAI
Portal.

## Verifying downloads

Each release includes a `sha256sums.txt` file. Verify your download against
it before installing.

## License

MIT — see [LICENSE](LICENSE). Nadia is built on hermes-agent by Nous Research
(MIT).

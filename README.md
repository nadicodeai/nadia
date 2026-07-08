# Nadia — the NadicodeAI agent

Nadia is an AI agent desktop app. Sign in with the
[NadicodeAI Portal](https://portal.nadicode.ai) to activate — your
subscription and models are managed there.

## Install

Download the latest release from the
[Releases page](https://github.com/nadicodeai/nadia/releases).

**macOS (Apple Silicon)** — `.dmg`

The app is ad-hoc signed for now. On first open, either run:

```
xattr -dr com.apple.quarantine /Applications/Nadia.app
```

or go to System Settings → Privacy & Security → Open Anyway.

**Linux (x86_64)** — `.AppImage` or `.deb`

```
chmod +x Nadia-*.AppImage
./Nadia-*.AppImage
```

Debian/Ubuntu users can instead install the `.deb` package.

**Windows** — coming soon.

## First launch

On first launch, Nadia installs its background agent from the source bundled
inside the app (about 2 minutes; requires network access to fetch
dependencies), then opens the portal sign-in screen.

## Verifying downloads

Each release includes a `sha256sums.txt` file. Verify your download against
it before installing.

## License

MIT — see [LICENSE](LICENSE). Nadia is built on hermes-agent by Nous Research
(MIT).

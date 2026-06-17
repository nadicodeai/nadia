# nadia

Nadia is the NadicodeAI-branded self-improving AI agent. Customers can install it as a CLI, use the native macOS or Windows desktop app, run the profile builder, or deploy the Docker image. It is maintained by [nadicodeai](https://github.com/nadicodeai) as a rebranded fork of NousResearch's [hermes-agent](https://github.com/NousResearch/hermes-agent); the agent's behavior tracks upstream weekly with a small set of fork-only patches applied on top.

## Install the CLI

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.sh | bash
```

The installer provisions Nadia, creates the `nadia` command, and starts the setup wizard. Tested on Ubuntu 22.04+; the install script also supports macOS, WSL2, and Termux.

Two optional flags: pass `--skip-setup` to skip the interactive Telegram wizard (`curl ... | bash -s -- --skip-setup`), or `--skip-browser` to skip Node/browser-tool provisioning on headless servers that lack `xz-utils`.

## Download the desktop app

macOS and Windows desktop installers are published as GitHub Release assets:

<https://github.com/nadicodeai/nadia/releases/latest>

Release asset names use the `Nadia-Agent-*` prefix and include `.dmg` for macOS and `.exe` for Windows when the release workflow completes successfully.

## Run with Docker

```bash
docker pull ghcr.io/nadicodeai/nadia:latest
docker run --rm -it ghcr.io/nadicodeai/nadia:latest nadia --help
```

To run interactively with a persistent home directory and an API key:

```bash
docker run --rm -it \
  -v "$HOME/.nadia:/home/nadia/.nadia" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  ghcr.io/nadicodeai/nadia:latest nadia
```

## Image variants

nadia ships in two flavours so you pick the one that matches your deployment shape.

| Tag                                                            | Size    | When to use                                                                                                                          |
| -------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `:latest`, `:v<X.Y.Z>`                                         | ~4.5 GB | **Default.** Full customer surface: TUI dashboard, voice mode, browser-tool MCP, s6-supervised dashboard + gateway. |
| `:slim`, `:latest-slim`, `:v<X.Y.Z>-slim`                      | ~371 MB | CLI-only deployments (CI runners, batch agents, server-side automation). Satisfies `nadia --help`, `--version`, `doctor`, `mcp`, `hooks`, `auth`, `sessions`. No TUI / voice / browser. |

## Fork notice

nadia is a fork of NousResearch's [hermes-agent](https://github.com/NousResearch/hermes-agent). All credit for the agent's design and core implementation belongs to NousResearch. nadicodeai maintains this fork to ship the Nadia-branded customer product; we track upstream's `main` branch on a weekly cron, re-apply a small fork-patch series, and publish the release tree, desktop installers, and GHCR image.

- Upstream project: <https://github.com/NousResearch/hermes-agent>
- Upstream docs: <https://hermes-agent.nousresearch.com/docs/>

## Issues

- For behavior shared with upstream (agent capabilities, model integrations, CLI semantics), prefer filing at <https://github.com/NousResearch/hermes-agent/issues>.
- For nadia-specific problems (the Docker image, packaging, our CI, the rebrand), file at <https://github.com/nadicodeai/nadia/issues>.

## Contributing

nadia's source tree keeps upstream pristine; fork additions live as a quilt patch series plus an overlay directory, and the hermes→nadia rebrand runs at build time. See [`AGENTS.md`](AGENTS.md) for the maintainer workflow and [`.shepherd/`](.shepherd/) for the full spec, plan, and standards.

## License

nadia inherits upstream's MIT license. See [`upstream/LICENSE`](upstream/LICENSE) for the full text and original copyright notice.

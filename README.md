# argo

argo is a self-improving AI agent distributed as a Docker image. It is maintained by [nadicodeai](https://github.com/nadicodeai) as a rebranded fork of NousResearch's [hermes-agent](https://github.com/NousResearch/hermes-agent); the agent's behavior tracks upstream weekly with a small set of fork-only patches applied on top.

## Quickstart

```bash
docker pull ghcr.io/nadicodeai/argo:latest
docker run --rm -it ghcr.io/nadicodeai/argo:latest argo --help
```

To run interactively with a persistent home directory and an API key:

```bash
docker run --rm -it \
  -v "$HOME/.argo:/home/argo/.argo" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  ghcr.io/nadicodeai/argo:latest argo
```

## Fork notice

argo is a fork of NousResearch's [hermes-agent](https://github.com/NousResearch/hermes-agent). All credit for the agent's design and core implementation belongs to NousResearch. nadicodeai maintains this fork to ship a rebranded image (`argo`) for our customer deployments; we track upstream's `main` branch on a weekly cron, re-apply a small fork-patch series, and publish to GHCR.

- Upstream project: <https://github.com/NousResearch/hermes-agent>
- Upstream docs: <https://hermes-agent.nousresearch.com/docs/>

## Issues

- For behavior shared with upstream (agent capabilities, model integrations, CLI semantics), prefer filing at <https://github.com/NousResearch/hermes-agent/issues>.
- For argo-specific problems (the Docker image, packaging, our CI, the rebrand), file at <https://github.com/nadicodeai/argo/issues>.

## Contributing

argo's source tree keeps upstream pristine; fork additions live as a quilt patch series plus an overlay directory, and the hermes→argo rebrand runs at build time. See [`AGENTS.md`](AGENTS.md) for the maintainer workflow and [`.shepherd/`](.shepherd/) for the full spec, plan, and standards.

## License

argo inherits upstream's MIT license. See [`upstream/LICENSE`](upstream/LICENSE) for the full text and original copyright notice.

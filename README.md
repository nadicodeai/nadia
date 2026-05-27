# argo

Self-improving AI agent. Distributed as a Docker image:

```bash
docker pull ghcr.io/nadicodeai/argo:latest
docker run --rm -it ghcr.io/nadicodeai/argo argo --help
```

## Quickstart

```bash
docker run --rm -it \
  -v "$HOME/.argo:/home/argo/.argo" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  ghcr.io/nadicodeai/argo:latest argo
```

## Fork notice

argo is a fork of NousResearch's [hermes-agent](https://github.com/NousResearch/hermes-agent), maintained by nadicodeai. We track upstream's `main` branch on a weekly cadence and apply a small set of rebranding and CI patches on top.

- Upstream docs: <https://hermes-agent.nousresearch.com>
- Upstream issues: file at [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/issues) for behavior shared with upstream; file [nadicodeai/argo](https://github.com/nadicodeai/argo/issues) for argo-specific issues.

## Contributing

See [`AGENTS.md`](AGENTS.md) for the development workflow. Source-of-truth documentation for maintainers lives under [`.shepherd/`](.shepherd/).

## License

Inherits upstream's license; see [`upstream/LICENSE`](upstream/LICENSE) once the subtree is populated.

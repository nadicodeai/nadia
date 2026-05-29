# Assertions for 0014-readme-rebrand-commands.patch
#
# The README quickstart must use the real `argo` command name and ~/.argo config
# path (the binary is argo; hermes is command-not-found). Pin a few rebranded
# command examples + the config path. Attribution survival (the upstream
# NousResearch/hermes-agent LICENSE link) is pinned by 0002's assertions.

path:README.md argo model
path:README.md argo setup
path:README.md ~/.argo
path:README.zh-CN.md argo model

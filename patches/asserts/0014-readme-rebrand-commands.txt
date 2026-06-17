# Assertions for 0014-readme-rebrand-commands.patch
#
# The README quickstart must use the real `nadia` command name and ~/.nadia config
# path (the binary is nadia; hermes is command-not-found). Pin a few rebranded
# command examples + the config path. Attribution survival (the upstream
# NousResearch/hermes-agent LICENSE link) is pinned by 0002's assertions.

path:README.md nadia model
path:README.md nadia setup
path:README.md ~/.nadia
path:README.zh-CN.md nadia model

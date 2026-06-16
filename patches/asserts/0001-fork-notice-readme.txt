# Assertions for 0001-fork-notice-readme.patch
#
# After `make build`, the patch must land in dist/nadia/README.md with:
#   - the literal fork-notice phrase ("Fork of NousResearch/hermes-agent"),
#   - the new repo URL slug ("nadicodeai/nadia"), proving the post-build
#     content names the renamed fork (not legacy nadicodeai/nadia-agent).
#
# Both patterns are restricted to README.md so an incidental hit elsewhere
# in dist/nadia/ (e.g. an upstream-installed file) cannot mask a real drop.

path:README.md Fork of NousResearch/hermes-agent
path:README.md nadicodeai/nadia

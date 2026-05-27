# Negative fixture: every brand-string occurrence in this file is
# covered by the skip_contexts regex (upstream-repo URL match). The
# scanner must NOT report any of these and must exit 0.
#
# Note: this comment block deliberately avoids the brand string outside
# URL form so the file is genuinely covered by skip_contexts alone.

UPSTREAM_URL = "https://github.com/NousResearch/hermes-agent/blob/main/README.md"
DOCS_URL = "https://github.com/NousResearch/hermes-agent/tree/main/docs"

# git-sha pin (40 hex chars) — skip_contexts covers 40-hex token leakage.
PIN_SHA = "a890389b69575916dfaf3980556f31f7f25c9871"

#!/bin/sh
# Minimal hook fixture for the parity runner.
# Both legacy and new images may or may not support `hook fire` /
# `hooks test`. The runner SKIPs the surface gracefully when either
# image lacks the subcommand. When the subcommand IS supported, this
# script echoes a deterministic line that the runner can diff after
# brand-string normalization.
echo "parity-fixture: event=${1:-unknown}"

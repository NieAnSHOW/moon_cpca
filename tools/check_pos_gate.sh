#!/usr/bin/env bash
# DR-01 call-site gate (spec §11.1.1): pos must count Unicode code points, so a
# `String::length()` call-site (UTF-16 code-unit width) in engine sources is
# forbidden. Comment lines are excluded; only executable call-sites fail.
#
# Usage: bash tools/check_pos_gate.sh
# Exit: 0 = no call-site; 1 = forbidden call-site found.
set -u

cd "$(dirname "$0")/.." || exit 2

if grep -nE '\.length\(\)' engine/*.mbt | grep -vE ':[0-9]+:[[:space:]]*//' | grep -q .; then
  echo "FORBIDDEN String::length() call-site" >&2
  exit 1
fi

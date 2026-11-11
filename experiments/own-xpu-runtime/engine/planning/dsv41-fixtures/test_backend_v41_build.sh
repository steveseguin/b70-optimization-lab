#!/usr/bin/env bash
# Compile the real runner in both activation modes without running GPU work.
# Usage: ICPX=/path/to/icpx bash planning/dsv41-fixtures/test_backend_v41_build.sh
set -euo pipefail

engine_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$engine_dir"
compiler="${ICPX:-icpx}"
common=(-fsycl -std=c++20 -I planning/dsv41-fixtures -I src -fsyntax-only)
source_file=planning/dsv41-fixtures/own_run_v41.cpp

"$compiler" "${common[@]}" "$source_file"
"$compiler" "${common[@]}" -DOWN41_ACT_BF16 "$source_file"

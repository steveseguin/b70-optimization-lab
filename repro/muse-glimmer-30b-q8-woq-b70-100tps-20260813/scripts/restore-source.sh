#!/usr/bin/env bash
set -euo pipefail

recipe_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
lab_root=$(cd "$recipe_root/../.." && pwd)
patch_file=$lab_root/patches/muse-glimmer-30b-b70/llama.cpp-030ebb558-to-q8-woq-century-20260813.patch
base=030ebb558a5820b444a8f836ed5cdd46c9b4bd7a
expected_patch=3965702b96fe18e2dc9110c7593fd33fbd68312e8321094b8b61b4656b380f19
destination=${1:-"$HOME/src/llama.cpp-muse-q8-woq-repro"}

if [[ -e $destination ]]; then
    echo "refusing to overwrite $destination" >&2
    exit 2
fi
printf '%s  %s\n' "$expected_patch" "$patch_file" | sha256sum -c -
git clone https://github.com/ggml-org/llama.cpp.git "$destination"
git -C "$destination" checkout --detach "$base"
git -C "$destination" apply --check --index "$patch_file"
git -C "$destination" apply --index "$patch_file"

actual=$(git -C "$destination" diff --cached --binary "$base" | sha256sum | awk '{print $1}')
if [[ $actual != "$expected_patch" ]]; then
    echo "restored tree differs from record patch: $actual" >&2
    exit 3
fi
echo "restored exact record source at $destination"
echo "the restored record delta is intentionally staged so newly added files remain part of the verified identity"

#!/bin/bash
# igc-dump-kernel.sh <kernel_substr> <out_dir> -- <command ...>:
# Safely dumps IGC shader assembly for kernels matching <kernel_substr>, copies matching .asm files
# to <out_dir>, and IMMEDIATELY deletes the multi-GB temporary IGC dump folder so root disk never fills.
set -eu
pattern=${1:?usage: igc-dump-kernel.sh <kernel_substr> <out_dir> -- <command ...>}
out_dir=${2:?usage: igc-dump-kernel.sh <kernel_substr> <out_dir> -- <command ...>}
shift 2
[ "${1:-}" = "--" ] && shift
[ "$#" -gt 0 ] || { echo "igc-dump-kernel: missing command after --"; exit 2; }

mkdir -p "$out_dir"
tmp_dump=$(mktemp -d /tmp/igc-dump.XXXXXX)
trap 'rm -rf -- "$tmp_dump"' EXIT

IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir="$tmp_dump" "$@"

copied=0
while IFS= read -r -d '' f; do
    cp -- "$f" "$out_dir/"
    copied=$((copied + 1))
done < <(find "$tmp_dump" -type f -name "*.asm" -iname "*${pattern}*" -print0)

echo "igc-dump-kernel: copied $copied matching .asm file(s) for '$pattern' into $out_dir (raw dump deleted)"
[ "$copied" -gt 0 ] || { echo "igc-dump-kernel: warning: 0 files matched '$pattern'"; exit 1; }

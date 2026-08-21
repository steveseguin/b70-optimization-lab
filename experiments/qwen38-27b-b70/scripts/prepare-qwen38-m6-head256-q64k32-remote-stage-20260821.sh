#!/usr/bin/env bash
set -euo pipefail

# Construct both canonical reference-host stages from one immutable incoming
# packet. This helper transfers and builds nothing; it only validates/copies.

repo=/home/steve/b70-optimization-lab
host=steve-TURIND8-2L2T
incoming=/home/steve/qwen38-m6-head256-q64k32-remote-transfer-20260821-r1
incoming_runtime=$incoming/runtime
incoming_candidate_graph=$incoming/qwen38-m6-head256-q64k32-r2-candidate.graph.sha256
incoming_control_graph=$incoming/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256
incoming_control_dso=$incoming/libattn_kernels_xe_2.control.so
root=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2
stage=$root/runtime
package=$stage/vllm_xpu_kernels
graph=$root/qwen38-m6-head256-q64k32-r2-candidate.graph.sha256
build_inputs=$root/qwen38-m6-head256-q64k32-r2-build-inputs.sha256
stage_json=$root/qwen38-m6-head256-q64k32-r2-candidate-stage.json
control=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
repo_control_graph=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256
patch=$repo/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-m6-head256-q64k32-chunk-prefill-r2-20260821.patch
builder=$repo/experiments/qwen38-27b-b70/scripts/build-qwen38-m6-head256-q64k32-attn-override-r2-20260821.sh
python=/home/steve/.venvs/vllm-xpu/bin/python

patch_sha=9386432015f5c9cd330dd7cfb785a16f259cce8563f44da9f812dcceb342138a
builder_sha=11480161dce25cba56e00f2f48c95d74164bac1f5af2dbc945eddceff6d57d47
extension_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
interface_sha=869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480
stock_sha=3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289
candidate_sha=01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5
control_sha=604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c
candidate_graph_sha=d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4
control_graph_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
schema=qwen38-mtp5-m6-fa-q64k32-r2-stage-v1

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
verify() {
  local path=$1 expected=$2 actual
  [[ -f $path ]] || die "missing required file: $path"
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  [[ $actual == "$expected" ]] || die "SHA mismatch: $path ($actual != $expected)"
}
graph_sha() {
  local selected_stage=$1
  (
    cd "$selected_stage"
    find vllm_xpu_kernels -type f -print0 |
      LC_ALL=C sort -z |
      xargs -0 sha256sum |
      sha256sum |
      awk '{print $1}'
  )
}
verify_tree() {
  local selected_stage=$1 selected_graph=$2 expected=$3 require_sealed=${4:-0}
  local directories
  [[ -z $(find "$selected_stage" ! -type d ! -type f -print -quit) ]] || \
    die "stage contains a nonregular node: $selected_stage"
  directories=$(cd "$selected_stage" && find . -mindepth 1 -type d -printf '%P\n' | LC_ALL=C sort)
  [[ $directories == $'vllm_xpu_kernels\nvllm_xpu_kernels/quantization' ]] || \
    die "stage directory inventory differs: $selected_stage"
  [[ $(find "$selected_stage" -type f | wc -l) -eq 20 ]] || \
    die "stage must contain exactly 20 total regular files: $selected_stage"
  [[ $(find "$selected_stage/vllm_xpu_kernels" -type f | wc -l) -eq 20 ]] || \
    die "stage must contain exactly 20 regular package files: $selected_stage"
  [[ $(graph_sha "$selected_stage") == "$expected" ]] || die "stage graph differs: $selected_stage"
  (cd "$selected_stage" && sha256sum --quiet -c "$selected_graph") || \
    die "stage files differ from graph manifest: $selected_stage"
  if [[ $require_sealed -eq 1 ]]; then
    [[ -z $(find "$selected_stage" -perm /222 -print -quit) ]] || \
      die "sealed stage contains a writable node: $selected_stage"
  fi
}
usage() {
  printf 'usage: %s --audit-source | --seal-transferred-stages\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
mode=$1
[[ $mode == --audit-source || $mode == --seal-transferred-stages ]] || usage
verify "$patch" "$patch_sha"
verify "$builder" "$builder_sha"
verify "$repo_control_graph" "$control_graph_sha"
if [[ $mode == --audit-source ]]; then
  printf 'PASS: remote two-stage transfer/seal source prerequisites are exact\n'
  exit 0
fi

[[ $(hostname) == "$host" ]] || die "seal is restricted to $host"
[[ $(realpath -e -- "$repo") == "$repo" ]] || die 'remote repo is absent/noncanonical'
[[ $(realpath -e -- "$incoming") == "$incoming" ]] || die 'incoming transfer root is absent/noncanonical'
[[ -x $python ]] || die "missing XPU Python: $python"
[[ ! -e $root && ! -e $control ]] || die 'both canonical stage roots must be absent'
incoming_entries=$(find "$incoming" -mindepth 1 -maxdepth 1 -printf '%f\n' | LC_ALL=C sort)
[[ $incoming_entries == $'libattn_kernels_xe_2.control.so\nqwen38-m6-head256-q64k32-r2-candidate.graph.sha256\nruntime\nstaged-xpu-commitfix-graphfa-composite-20260820.graph.sha256' ]] || \
  die 'incoming transfer packet inventory differs'
[[ -z $(find "$incoming" -mindepth 1 -maxdepth 1 ! -type d ! -type f -print -quit) ]] || \
  die 'incoming transfer packet contains a nonregular node'
candidate_tmp=/home/steve/.qwen38-q64k32-candidate-stage.tmp.$$
control_tmp=/home/steve/.qwen38-q64k32-control-stage.tmp.$$
[[ ! -e $candidate_tmp && ! -e $control_tmp ]] || die 'private stage temporary path collision'
complete=false
candidate_identity=
control_identity=
remove_private_tree() {
  local selected=$1
  [[ ! -e $selected ]] || {
    chmod -R u+w -- "$selected"
    rm -rf -- "$selected"
  }
}
cleanup() {
  trap '' EXIT INT TERM HUP
  remove_private_tree "$candidate_tmp"
  remove_private_tree "$control_tmp"
  if [[ $complete != true ]]; then
    [[ -z $candidate_identity || ! -e $root || \
       $(stat -c '%d:%i' -- "$root") != "$candidate_identity" ]] || \
      remove_private_tree "$root"
    [[ -z $control_identity || ! -e $control || \
       $(stat -c '%d:%i' -- "$control") != "$control_identity" ]] || \
      remove_private_tree "$control"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

verify "$incoming_candidate_graph" "$candidate_graph_sha"
verify "$incoming_control_graph" "$control_graph_sha"
cmp -s -- "$incoming_control_graph" "$repo_control_graph" || \
  die 'incoming and tracked control graph manifests differ'
verify "$incoming_control_dso" "$control_sha"
verify "$incoming_runtime/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$extension_sha"
verify "$incoming_runtime/vllm_xpu_kernels/flash_attn_interface.py" "$interface_sha"
verify "$incoming_runtime/vllm_xpu_kernels/libattn_stock.so" "$stock_sha"
verify "$incoming_runtime/vllm_xpu_kernels/libattn_kernels_xe_2.so" "$candidate_sha"
verify_tree "$incoming_runtime" "$incoming_candidate_graph" "$candidate_graph_sha" 0

mkdir -- "$candidate_tmp"
candidate_identity=$(stat -c '%d:%i' -- "$candidate_tmp")
cp -R --reflink=auto --preserve=mode,timestamps -- \
  "$incoming_runtime" "$candidate_tmp/runtime"
cp --preserve=mode,timestamps -- "$incoming_candidate_graph" \
  "$candidate_tmp/qwen38-m6-head256-q64k32-r2-candidate.graph.sha256"

candidate_tmp_stage=$candidate_tmp/runtime
candidate_tmp_package=$candidate_tmp_stage/vllm_xpu_kernels
candidate_tmp_graph=$candidate_tmp/qwen38-m6-head256-q64k32-r2-candidate.graph.sha256
candidate_tmp_build=$candidate_tmp/qwen38-m6-head256-q64k32-r2-build-inputs.sha256
candidate_tmp_json=$candidate_tmp/qwen38-m6-head256-q64k32-r2-candidate-stage.json
printf '%s  %s\n' \
  "$patch_sha" "$patch" \
  "$builder_sha" "$builder" \
  "$candidate_sha" "$package/libattn_kernels_xe_2.so" \
  "$candidate_graph_sha" "$graph" >"$candidate_tmp_build"
build_sha=$(sha256sum -- "$candidate_tmp_build" | awk '{print $1}')

"$python" -B - "$candidate_tmp_json" "$schema" "$stage" "$build_inputs" \
  "$build_sha" "$extension_sha" "$interface_sha" "$candidate_sha" "$stock_sha" <<'PY'
import json
import os
from pathlib import Path
import sys

output_text, schema, stage, artifact, artifact_sha, extension, interface, device, stock = sys.argv[1:]
output = Path(output_text)
payload = {
    "artifact": {"path": artifact, "sha256": artifact_sha},
    "files": {
        "device_library": {"relative_path": "vllm_xpu_kernels/libattn_kernels_xe_2.so", "sha256": device},
        "extension": {"relative_path": "vllm_xpu_kernels/_vllm_fa2_C.abi3.so", "sha256": extension},
        "interface": {"relative_path": "vllm_xpu_kernels/flash_attn_interface.py", "sha256": interface},
        "stock_library": {"relative_path": "vllm_xpu_kernels/libattn_stock.so", "sha256": stock},
    },
    "role": "candidate",
    "schema": schema,
    "stage": stage,
}
encoded = (json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n").encode()
fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
with os.fdopen(fd, "wb") as stream:
    stream.write(encoded)
    stream.flush()
    os.fsync(stream.fileno())
PY
chmod 0444 "$candidate_tmp_build" "$candidate_tmp_graph" "$candidate_tmp_json"
find "$candidate_tmp_stage" -type f -exec chmod a-w -- {} +
find "$candidate_tmp_stage" -type d -exec chmod 0555 -- {} +
chmod 0555 "$candidate_tmp"
verify_tree "$candidate_tmp_stage" "$candidate_tmp_graph" "$candidate_graph_sha" 1

# Canonical candidate files must not alias the mutable incoming transfer tree.
while IFS= read -r -d '' candidate_file; do
  relative=${candidate_file#"$candidate_tmp_stage/"}
  [[ $(stat -c '%d:%i' -- "$candidate_file") != \
     $(stat -c '%d:%i' -- "$incoming_runtime/$relative") ]] || \
    die "candidate file aliases mutable incoming packet: $relative"
done < <(find "$candidate_tmp_stage/vllm_xpu_kernels" -type f -print0)

mkdir -- "$control_tmp"
control_identity=$(stat -c '%d:%i' -- "$control_tmp")
cp -al -- "$candidate_tmp_stage/." "$control_tmp/"
chmod u+w "$control_tmp/vllm_xpu_kernels"
rm -- "$control_tmp/vllm_xpu_kernels/libattn_kernels_xe_2.so"
install -m 0555 -- "$incoming_control_dso" \
  "$control_tmp/vllm_xpu_kernels/libattn_kernels_xe_2.so"
chmod 0555 "$control_tmp/vllm_xpu_kernels" "$control_tmp"
verify_tree "$control_tmp" "$incoming_control_graph" "$control_graph_sha" 1

# The 19 common files must be the exact efficient hardlink boundary. The two
# selected device DSOs must be distinct inodes and exact bytes.
while IFS= read -r -d '' candidate_file; do
  relative=${candidate_file#"$candidate_tmp_stage/"}
  [[ $relative == vllm_xpu_kernels/libattn_kernels_xe_2.so ]] && continue
  [[ $(stat -c '%d:%i' -- "$candidate_file") == \
     $(stat -c '%d:%i' -- "$control_tmp/$relative") ]] || \
    die "common stage file is not hardlinked: $relative"
done < <(find "$candidate_tmp_stage/vllm_xpu_kernels" -type f -print0)
[[ $(stat -c '%d:%i' -- "$candidate_tmp_package/libattn_kernels_xe_2.so") != \
   $(stat -c '%d:%i' -- "$control_tmp/vllm_xpu_kernels/libattn_kernels_xe_2.so") ]] || \
  die 'control and candidate device DSOs share an inode'

mv -- "$candidate_tmp" "$root"
mv -- "$control_tmp" "$control"
verify_tree "$control" "$repo_control_graph" "$control_graph_sha" 1
verify_tree "$stage" "$graph" "$candidate_graph_sha" 1
complete=true
trap - EXIT INT TERM HUP
printf 'PASS: canonical control and candidate stages sealed\n'
printf 'control_graph_sha256=%s\n' "$control_graph_sha"
printf 'candidate_graph_sha256=%s\n' "$candidate_graph_sha"
printf 'build_inputs_sha256=%s\n' "$build_sha"
printf 'stage_json_sha256=%s\n' "$(sha256sum -- "$stage_json" | awk '{print $1}')"

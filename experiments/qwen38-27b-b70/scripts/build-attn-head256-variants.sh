#!/usr/bin/env bash
# Build the flash-attention pieces of vllm-xpu-kernels 0.1.14.1 (6d92b1b) with one head-size-256
# chunk-prefill tile policy, for the 2026-10-17 prompt-attention timing study.
#   control   policy unchanged: QK <256,32,32>  PV <256,32,32>  Out <256,256>  SG <32,1,1>
#   k64       64 keys a step:   QK <256,64,32>  PV <256,32,64>  Out <256,256>  SG <32,1,1>
#   k64pv64   k64 fallback:     QK <256,64,32>  PV <256,64,64>  Out <256,256>  SG <32,1,1>
#   q128      128 query rows:   QK <128,32,32>  PV <128,32,32>  Out <128,256>  SG <16,1,1>
# (ShapeQK = <q rows, keys, head-dim chunk>, ShapePV = <q rows, out-dim chunk, keys>.)
#
# Output: $ROOT/<variant>/ _vllm_fa2_C.abi3.so, libattn_kernels_xe_2.so, BUILD.txt, logs/, checks/
#
# CPU only. The compile runs in the lab's upstream-toolchain builder image (DPC++ 2026.0.0.20260331,
# IGC 2.34.4, ocloc 26.18: the compiler named in the image wheel's .comment) against the sycl-tla
# revision the kernel CMake pins (87f6850). No GPU device, no network, a hard memory cap and no swap.
# Docker containers live in their own cgroup, so the cap is docker's --memory (= --memory-swap),
# not a systemd user scope. Run the script itself in a systemd user unit; builds take a while.
#
# Usage: build-attn-head256-variants.sh <control|k64|k64pv64|q128>
#   JOBS=1 (ninja jobs)  MEM=8g (container cap)  MIN_AVAIL_MIB=10240 (host MemAvailable floor)
#   RESUME=1 keeps the source and work trees and only reruns the build steps.
#   DECODE_LINE=8,64,16,false,false,false (paged-decode config line, see below)
#
# Paged decode: flash_attn_varlen_func defaults to is_mix_batch=True, and then every prefill call also
# launches the paged decode kernel (it skips prefill rows); for the study's shape that needs
# DECODE_LINE=8,256,64,false,false,false (decode is always non-causal). That TU was OOM-killed at the
# 8 GiB cap (one clang frontend > 8 GiB), so the default is the smallest decode config, and the
# benchmark must call with is_mix_batch=False (prefill-only path, chunk-prefill kernel only).
# Without it the call does not fail: the "not compiled" error is caught in Python and the whole
# call silently falls back to PyTorch reference attention (one stderr warning).
set -euo pipefail

CLEAN_SRC=${CLEAN_SRC:-/home/steve/builds/rebase-v0290-kernels-cleanclone-20260913/vllm-xpu-kernels}
COMMIT=${COMMIT:-6d92b1b}
ROOT=${ROOT:-/mnt/fast-ai/builds/attn-variants-20261017}
CUTLASS_SRC=${CUTLASS_SRC:-/mnt/fast-ai/build/sycl-tla-87f6850}
CUTLASS_REV=87f6850680a580654b9ea2c80dbc01aeb36ad231
# oneDNN is only configured (find_package is unconditional); nothing from it is compiled or linked here.
ONEDNN_SRC=${ONEDNN_SRC:-/home/steve/builds/rebase-v0290-kernels-cleanclone-20260913/onednn}
BUILDER=${BUILDER:-neural-download/vllm-xpu-kernels-builder:r312d-b}
RUNTIME_IMAGE=${RUNTIME_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride}
# The B70 (PCI 0xE223) reports IP 20.2.0 = bmg-g31-a0; bmg-g21-a0 is 20.1.0. Level Zero loads a native
# binary only for the exact IP (otherwise it rebuilds from the embedded SPIR-V with the runtime's IGC),
# and the image's wheel carries both members with identical code, so build both.
AOT_DEVICES=${AOT_DEVICES:-bmg-g21-a0,bmg-g31-a0}
# 7g OOM-killed the head-256 chunk-prefill TU (one clang frontend > 7 GiB); 8g is the agreed ceiling
MEM=${MEM:-8g}
JOBS=${JOBS:-1}
MIN_AVAIL_MIB=${MIN_AVAIL_MIB:-10240}
DECODE_LINE=${DECODE_LINE:-8,64,16,false,false,false}
DECODE_CONF=paged_decode_${DECODE_LINE//,/_}.conf
SITE=/opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels

# ---------------------------------------------------------------------------------------------
# Inside the builder container.
# ---------------------------------------------------------------------------------------------
inner() {
  export HOME=/work/home TMPDIR=/work/tmp RSS_LOG=/work/step-rss.log
  mkdir -p "$HOME" "$TMPDIR"
  : > "$RSS_LOG"
  # cgroup memory stats are written even when the build fails
  trap 'cat /sys/fs/cgroup/memory.peak > /work/cgroup-memory.peak 2>/dev/null || true;
        cat /sys/fs/cgroup/memory.events > /work/cgroup-memory.events 2>/dev/null || true' EXIT
  # the oneAPI env script is not nounset-safe
  set +u
  source /opt/oneapi-2026.0/compiler/2026.0/env/vars.sh > /work/oneapi-env.log 2>&1
  source /opt/venv/bin/activate
  set -u
  export VLLM_XPU_AOT_DEVICES="$AOT_DEVICES" VLLM_XPU_XE2_AOT_DEVICES="$AOT_DEVICES"
  export VLLM_CUTLASS_SRC_DIR=/deps/cutlass
  {
    icpx --version | head -1
    echo "ocloc $(ocloc --version 2>&1 | head -1)"
    dpkg-query -W intel-igc-core-2 intel-ocloc
    python3 -c 'import torch; print("torch", torch.__version__, torch.version.git_version)'
    cmake --version | head -1
    echo "ninja $(ninja --version)"
    gcc --version | head -1
  } > /work/toolchain.txt 2>&1

  # Launcher: runs one compile/link command and logs the peak RSS of its largest child process.
  cat > /work/rss-launcher.py <<'PY'
#!/usr/bin/env python3
import os, resource, subprocess, sys, time
argv = sys.argv[1:]
t = time.time()
rc = subprocess.call(argv)
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1048576
target = argv[argv.index("-o") + 1] if "-o" in argv else argv[-1]
with open(os.environ.get("RSS_LOG", "/dev/null"), "a") as f:
    f.write(f"{peak:.2f} GiB\t{time.time() - t:.0f} s\trc={rc}\t{os.path.basename(target)}\n")
sys.exit(rc if rc >= 0 else 128 - rc)
PY
  chmod +x /work/rss-launcher.py

  local args=(
    -S /src -B /work/build -G Ninja
    -DCMAKE_BUILD_TYPE=Release
    -DVLLM_TARGET_DEVICE=xpu
    -DCMAKE_TOOLCHAIN_FILE=/src/cmake/toolchain.cmake
    -DVLLM_PYTHON_EXECUTABLE="$(which python3)"
    -DVLLM_PYTHON_PATH="$(python3 -c 'import sys; print(":".join(sys.path))')"
    -DFETCHCONTENT_BASE_DIR=/work/fetchcontent
    -DFETCHCONTENT_SOURCE_DIR_ONEDNN=/deps/onednn
    -DBUILD_SYCL_TLA_KERNELS=ON
    -DVLLM_XPU_ENABLE_XE2=ON
    -DVLLM_XPU_ENABLE_XE_DEFAULT=OFF
    -DFA2_KERNELS_ENABLED=ON
    -DBASIC_KERNELS_ENABLED=OFF
    -DMOE_KERNELS_ENABLED=OFF
    -DGDN_KERNELS_ENABLED=OFF
    -DMQA_LOGITS_KERNELS_ENABLED=OFF
    -DMHC_KERNELS_ENABLED=OFF
    -DXPU_SPECIFIC_KERNELS_ENABLED=OFF
    -DXPUMEM_ALLOCATOR_ENABLED=OFF
    -DVLLM_CHUNK_PREFILL_CONFIG=/configs/chunk_prefill_head256_paged_causal.conf
    -DVLLM_PAGED_DECODE_CONFIG="/configs/$DECODE_CONF"
    -DCMAKE_CXX_COMPILER_LAUNCHER=/work/rss-launcher.py
    -DCMAKE_CXX_LINKER_LAUNCHER=/work/rss-launcher.py
  )
  printf '%q ' cmake "${args[@]}" > /work/cmake-command.txt
  echo "VLLM_XPU_AOT_DEVICES=$AOT_DEVICES VLLM_XPU_XE2_AOT_DEVICES=$AOT_DEVICES VLLM_CUTLASS_SRC_DIR=/deps/cutlass" \
    >> /work/cmake-command.txt
  echo "### configure $(date -u +%T)"
  cmake "${args[@]}" > /work/configure.log 2>&1
  echo "### build -j$JOBS $(date -u +%T)"
  cmake --build /work/build -j "$JOBS" --target attn_kernels_xe_2 _vllm_fa2_C -- -v > /work/build.log 2>&1
  echo "### install $(date -u +%T)"
  rm -rf /work/install
  # the top-level install sets CMAKE_INSTALL_LOCAL_ONLY, so the attention library is installed from
  # its own subdirectory (this also rewrites its RUNPATH to $ORIGIN, as in the wheel)
  cmake --install /work/build/csrc/xpu/attn/xe_2 --prefix /work/install >> /work/build.log 2>&1
  cmake --install /work/build --prefix /work/install --component _vllm_fa2_C >> /work/build.log 2>&1
  find /work/build -name '*enabled_policies_gen.hpp' -exec cp {} /work/ \;
  echo "### done $(date -u +%T)"
}

if [[ "${1:-}" == --inner ]]; then
  inner
  exit 0
fi

# ---------------------------------------------------------------------------------------------
# On the host.
# ---------------------------------------------------------------------------------------------
variant=${1:?usage: $0 <control|k64|k64pv64|q128>}
case "$variant" in
  control) qk="_256, _32, _32"; pv="_256, _32, _32"; o="_256, _256"; sg="_32, _1, _1";;
  k64)     qk="_256, _64, _32"; pv="_256, _32, _64"; o="_256, _256"; sg="_32, _1, _1";;
  k64pv64) qk="_256, _64, _32"; pv="_256, _64, _64"; o="_256, _256"; sg="_32, _1, _1";;
  q128)    qk="_128, _32, _32"; pv="_128, _32, _32"; o="_128, _256"; sg="_16, _1, _1";;
  *) echo "unknown variant: $variant" >&2; exit 1;;
esac
self=$(readlink -f -- "${BASH_SOURCE[0]}")
out=$ROOT/$variant
src=$ROOT/src-$variant
work=$ROOT/work-$variant
cfg=$ROOT/configs
mkdir -p "$out/logs" "$out/checks" "$cfg"
say() { echo "### $(date +%T) [$variant] $*"; }

# Kernel configs: only the shapes the timing study runs.
cat > "$cfg/chunk_prefill_head256_paged_causal.conf" <<'EOF'
# head 256, paged, causal, no window, no sink, no lse: the only chunk-prefill shape the study calls
# (the cmake mechanism also generates the matching _b16 policy for page size 16)
256,true,true,false,false,false
EOF
{
  echo "# paged decode: $DECODE_LINE (see the header of build-attn-head256-variants.sh)"
  echo "$DECODE_LINE"
} > "$cfg/$DECODE_CONF"

# Pinned dependencies.
[[ "$(git -C "$CUTLASS_SRC" rev-parse HEAD)" == "$CUTLASS_REV" ]] || { echo "sycl-tla is not at $CUTLASS_REV" >&2; exit 1; }
[[ -z "$(git -C "$CUTLASS_SRC" status --porcelain)" ]] || { echo "sycl-tla checkout has local changes" >&2; exit 1; }
commit_full=$(git -C "$CLEAN_SRC" rev-parse "$COMMIT^{commit}")

# Fresh source: a clone of the clean tree at the commit, plus only the policy change.
if [[ "${RESUME:-0}" != 1 ]]; then
  rm -rf "$src" "$work"
  git clone --quiet --no-checkout "$CLEAN_SRC" "$src"
  git -C "$src" checkout --quiet --detach "$commit_full"
  python3 - "$src/csrc/xpu/attn/xe_2/fmha_utils.hpp" "$qk" "$pv" "$o" "$sg" <<'PY'
import sys
path, qk, pv, o, sg = sys.argv[1:]
old = ("struct chunk_policy_head256 {\n"
       "  using ShapeQK = Shape<_256, _32, _32>;\n"
       "  using ShapePV = Shape<_256, _32, _32>;\n"
       "  using ShapeOut = Shape<_256, _256>;\n"
       "  using SubgroupLayoutQK = Layout<Shape<_32, _1, _1>>;\n"
       "};\n")
new = ("struct chunk_policy_head256 {\n"
       f"  using ShapeQK = Shape<{qk}>;\n"
       f"  using ShapePV = Shape<{pv}>;\n"
       f"  using ShapeOut = Shape<{o}>;\n"
       f"  using SubgroupLayoutQK = Layout<Shape<{sg}>>;\n"
       "};\n")
text = open(path).read()
assert text.count(old) == 1, "head256 policy block not found exactly once"
open(path, "w").write(text.replace(old, new))
PY
fi
git -C "$src" diff > "$out/policy.diff"
changed=$(git -C "$src" status --porcelain)
if [[ "$variant" == control ]]; then
  [[ -z "$changed" ]] || { echo "control source differs from $commit_full: $changed" >&2; exit 1; }
else
  [[ "$changed" == " M csrc/xpu/attn/xe_2/fmha_utils.hpp" ]] || { echo "unexpected source changes: $changed" >&2; exit 1; }
fi
mkdir -p "$work"

# Host memory floor.
free -m > "$out/logs/free-before.txt"
avail=$(awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo)
(( avail >= MIN_AVAIL_MIB )) || { echo "only ${avail} MiB available, need ${MIN_AVAIL_MIB}" >&2; exit 2; }
say "MemAvailable ${avail} MiB; building with -j$JOBS under a $MEM cap"

t0=$(date +%s)
set +e
docker run --rm --name "attn-build-$variant" --network none --memory "$MEM" --memory-swap "$MEM" \
  --user "$(id -u):$(id -g)" \
  -v "$src:/src:ro" -v "$work:/work" -v "$cfg:/configs:ro" \
  -v "$ONEDNN_SRC:/deps/onednn:ro" -v "$CUTLASS_SRC:/deps/cutlass:ro" -v "$self:/build.sh:ro" \
  -e AOT_DEVICES="$AOT_DEVICES" -e JOBS="$JOBS" -e DECODE_LINE="$DECODE_LINE" \
  --entrypoint /bin/bash "$BUILDER" /build.sh --inner
rc=$?
set -e
wall=$(( $(date +%s) - t0 ))
for f in toolchain.txt cmake-command.txt configure.log build.log step-rss.log cgroup-memory.peak cgroup-memory.events \
         chunk_prefill_enabled_policies_gen.hpp paged_decode_enabled_policies_gen.hpp; do
  [[ -f "$work/$f" ]] && cp "$work/$f" "$out/logs/"
done
[[ -f "$work/build/compile_commands.json" ]] && cp "$work/build/compile_commands.json" "$out/logs/"
free -m > "$out/logs/free-after.txt"
if (( rc != 0 )); then
  say "BUILD FAILED rc=$rc after ${wall} s"
  grep -n -E "error|static_assert|Killed|out of memory|register" "$work/build.log" 2>/dev/null | head -40 || true
  tail -20 "$work/build.log" 2>/dev/null || true
  cat "$work/cgroup-memory.events" 2>/dev/null || true
  printf 'variant %s FAILED rc=%s after %s s; see logs/build.log\n' "$variant" "$rc" "$wall" > "$out/BUILD-FAILED.txt"
  exit "$rc"
fi
rm -f "$out/BUILD-FAILED.txt"
install -m 0755 "$work/install/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" "$out/_vllm_fa2_C.abi3.so"
install -m 0755 "$work/install/vllm_xpu_kernels/libattn_kernels_xe_2.so" "$out/libattn_kernels_xe_2.so"
say "built in ${wall} s"

# Reference copies of the image's two files.
ref=$ROOT/image-ref
if [[ ! -f "$ref/libattn_kernels_xe_2.so" || ! -f "$ref/_vllm_fa2_C.abi3.so" ]]; then
  mkdir -p "$ref"
  docker run --rm --network none --user "$(id -u):$(id -g)" -v "$ref:/out" --entrypoint /bin/bash "$RUNTIME_IMAGE" \
    -c "cp -p $SITE/_vllm_fa2_C.abi3.so $SITE/libattn_kernels_xe_2.so /out/"
fi

# Link checks: NEEDED/RUNPATH, and every symbol the binding takes from the attention library.
c=$out/checks
readelf -d "$out/_vllm_fa2_C.abi3.so" | grep -E "NEEDED|RPATH|RUNPATH" > "$c/binding-dynamic.txt" || true
readelf -d "$out/libattn_kernels_xe_2.so" | grep -E "NEEDED|RPATH|RUNPATH|SONAME" > "$c/lib-dynamic.txt" || true
ldd "$out/_vllm_fa2_C.abi3.so" > "$c/binding-ldd-host.txt" 2>&1 || true
nm -D --undefined-only "$out/_vllm_fa2_C.abi3.so" | awk '{print $NF}' | sort -u > "$c/binding-undefined.txt"
nm -D --defined-only "$out/libattn_kernels_xe_2.so" | awk '{print $NF}' | sort -u > "$c/lib-defined.txt"
nm -D --defined-only "$ref/libattn_kernels_xe_2.so" | awk '{print $NF}' | sort -u > "$c/image-lib-defined.txt"
nm -D --undefined-only "$ref/_vllm_fa2_C.abi3.so" | awk '{print $NF}' | sort -u > "$c/image-binding-undefined.txt"
comm -12 "$c/binding-undefined.txt" "$c/image-lib-defined.txt" > "$c/binding-needs-from-attn-lib.txt"
comm -23 "$c/binding-needs-from-attn-lib.txt" "$c/lib-defined.txt" > "$c/missing-from-new-lib.txt"
diff "$c/image-binding-undefined.txt" "$c/binding-undefined.txt" > "$c/binding-undefined-vs-image.diff" || true
dispatch_syms() { nm -D --defined-only "$1" | c++filt | awk '/policy_dispatch_impl/ {$1 = ""; sub(/^ /, ""); print}' | sort; }
dispatch_syms "$out/libattn_kernels_xe_2.so" > "$c/lib-dispatch-symbols.txt"
dispatch_syms "$ref/libattn_kernels_xe_2.so" > "$c/image-lib-dispatch-symbols.txt"
comm -23 "$c/lib-dispatch-symbols.txt" "$c/image-lib-dispatch-symbols.txt" > "$c/dispatch-symbols-not-in-image.txt"
link_ok=yes
grep -q 'NEEDED.*\[libattn_kernels_xe_2.so\]' "$c/binding-dynamic.txt" || link_ok=no
grep -q 'RUNPATH.*\[\$ORIGIN\]' "$c/binding-dynamic.txt" || link_ok=no
grep -q 'SONAME.*\[libattn_kernels_xe_2.so\]' "$c/lib-dynamic.txt" || link_ok=no
[[ -s "$c/missing-from-new-lib.txt" ]] && link_ok=no
grep -q "libattn_kernels_xe_2.so => $out/libattn_kernels_xe_2.so" "$c/binding-ldd-host.txt" || link_ok=no

# CPU-only import check in the runtime image with both files mounted over the image's copies (no GPU device).
docker run --rm --network none --memory 4g --memory-swap 4g -w / \
  -v "$out/_vllm_fa2_C.abi3.so:$SITE/_vllm_fa2_C.abi3.so:ro" \
  -v "$out/libattn_kernels_xe_2.so:$SITE/libattn_kernels_xe_2.so:ro" \
  --entrypoint /bin/bash "$RUNTIME_IMAGE" -c "
    LD_LIBRARY_PATH=/opt/venv/lib/python3.12/site-packages/torch/lib:/opt/venv/lib ldd $SITE/_vllm_fa2_C.abi3.so | grep -E 'attn|not found'
    python3 -c 'import vllm_xpu_kernels.flash_attn_interface as f; print(\"ok\")'
    python3 - <<'PY'
import hashlib, torch
import vllm_xpu_kernels.flash_attn_interface as f
print('FA2_AVAILABLE', f.FA2_AVAILABLE, f.FA2_UNAVAILABLE_REASON)
import vllm_xpu_kernels._vllm_fa2_C
print('varlen_fwd registered', hasattr(torch.ops._vllm_fa2_C, 'varlen_fwd'))
maps = sorted({l.split()[-1] for l in open('/proc/self/maps') if 'vllm_xpu_kernels' in l and l.rstrip().endswith('.so')})
for p in maps:
    print('mapped', p, hashlib.sha256(open(p, 'rb').read()).hexdigest())
print('IMPORT-CHECK', 'PASS' if f.FA2_AVAILABLE else 'FAIL')
PY" > "$c/import-check.txt" 2>&1 || true
import_ok=no
grep -q "IMPORT-CHECK PASS" "$c/import-check.txt" && import_ok=yes

# BUILD.txt
sha_b=$(sha256sum "$out/_vllm_fa2_C.abi3.so" | cut -d' ' -f1)
sha_l=$(sha256sum "$out/libattn_kernels_xe_2.so" | cut -d' ' -f1)
peak_cg=$(awk '{printf "%.2f GiB", $1 / 1073741824}' "$out/logs/cgroup-memory.peak" 2>/dev/null || echo unknown)
peak_step=$(sort -rn "$out/logs/step-rss.log" | awk -F'\t' 'NR == 1 {print $1 " (" $4 ")"}')
{
  echo "variant: $variant"
  echo "built: $(date -u +%FT%TZ) on $(hostname)"
  echo "source: $CLEAN_SRC at $commit_full ($(git -C "$src" describe --tags 2>/dev/null)), cloned to $src"
  echo "sycl-tla: $CUTLASS_SRC at $CUTLASS_REV (the CUTLASS_REVISION the kernel CMake pins)"
  echo "builder image: $BUILDER $(docker image inspect -f '{{.Id}}' "$BUILDER")"
  echo "runtime image (checks): $RUNTIME_IMAGE $(docker image inspect -f '{{.Id}}' "$RUNTIME_IMAGE")"
  echo
  echo "policy diff (empty for control):"
  if [[ -s "$out/policy.diff" ]]; then cat "$out/policy.diff"; else echo "  (none)"; fi
  echo
  echo "toolchain:"; sed 's/^/  /' "$out/logs/toolchain.txt"
  echo
  echo "kernel configs:"
  echo "  chunk prefill: $(grep -v '^#' "$cfg/chunk_prefill_head256_paged_causal.conf") (+ generated _b16 twin)"
  echo "  paged decode:  $(grep -v '^#' "$cfg/$DECODE_CONF")"
  if [[ "$DECODE_LINE" != 8,256,64,false,false,false ]]; then
    echo "  NOTE: no head-256 decode kernel. Call flash_attn_varlen_func with is_mix_batch=False, otherwise the"
    echo "        call silently falls back to PyTorch reference attention (caught 'not compiled' error)."
  fi
  echo
  echo "cmake command (inside the builder container):"; sed 's/^/  /' "$out/logs/cmake-command.txt"; echo
  echo "build: cmake --build -j$JOBS --target attn_kernels_xe_2 _vllm_fa2_C; container cap $MEM, no swap, no network, no GPU"
  echo "wall time: ${wall} s (configure + build + install, container start to exit)"
  echo "peak memory: container cgroup memory.peak $peak_cg (includes page cache); largest single process ${peak_step}"
  echo "per-step peak RSS (largest child), time, target:"; sed 's/^/  /' "$out/logs/step-rss.log"
  echo "cgroup memory.events:"; sed 's/^/  /' "$out/logs/cgroup-memory.events" 2>/dev/null || true
  echo
  echo "outputs:"
  echo "  $sha_b  $out/_vllm_fa2_C.abi3.so ($(stat -c %s "$out/_vllm_fa2_C.abi3.so") bytes)"
  echo "  $sha_l  $out/libattn_kernels_xe_2.so ($(stat -c %s "$out/libattn_kernels_xe_2.so") bytes)"
  echo
  echo "link check: $link_ok"
  grep -E "attn|RUNPATH" "$c/binding-dynamic.txt" | sed 's/^/  binding: /' || true
  grep -E "SONAME|RUNPATH" "$c/lib-dynamic.txt" | sed 's/^/  lib: /' || true
  echo "  binding symbols taken from the attention lib: $(wc -l < "$c/binding-needs-from-attn-lib.txt"), missing from the new lib: $(wc -l < "$c/missing-from-new-lib.txt")"
  echo "  binding undefined symbols vs image binding: $(grep -c '^[<>]' "$c/binding-undefined-vs-image.diff" || true) lines differ"
  echo "  host ldd: $(grep libattn "$c/binding-ldd-host.txt" | xargs || true)"
  echo "  dispatch symbols in the new lib:"; sed 's/^/    /' "$c/lib-dispatch-symbols.txt"
  echo "  of those, not in the image lib: $(wc -l < "$c/dispatch-symbols-not-in-image.txt")"
  echo
  echo "import check (runtime image, no GPU device): $import_ok"; sed 's/^/  /' "$c/import-check.txt"
} > "$out/BUILD.txt"
say "link check $link_ok, import check $import_ok"
say "$sha_b  _vllm_fa2_C.abi3.so"
say "$sha_l  libattn_kernels_xe_2.so"
[[ "$link_ok" == yes && "$import_ok" == yes ]]

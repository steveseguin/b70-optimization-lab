#!/usr/bin/env bash
# Clean-clone replay of the published R220 + R221 kernel-library chain (2026-09-06), closing the manifest's
# clean_source_build=false note. The two published build scripts run byte-identical; the only difference is that git's
# url.<base>.insteadOf rewriting points the three GitHub clone URLs at local bare mirrors of the pinned commits
# (made with `git clone --bare` from the original R220 build root; heads verified before use) because the host WAN
# was crawling at ~0.6 MB/s. Commit identity is still enforced by the scripts' own `checkout --detach <sha>`.
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
mirrors=${MIRRORS:-/home/steve/builds/mirrors-20260906}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
build_root=${BUILD_ROOT:-/home/steve/builds/w4a16-r220-r221-clean-clone-replay-${stamp}}
log_dir=${lab}/experiments/qwen38-27b-b70/data/replay-w4a16-r220-r221-clean-clone-${stamp}
mkdir -p "${log_dir}"
for s in vllm-xpu-kernels onednn sycl-tla; do git -C "${mirrors}/${s}.git" rev-parse HEAD > "${log_dir}/mirror-${s}-head.txt"; done
export GIT_CONFIG_COUNT=3
export GIT_CONFIG_KEY_0=url.file://${mirrors}/vllm-xpu-kernels.git.insteadOf GIT_CONFIG_VALUE_0=https://github.com/vllm-project/vllm-xpu-kernels.git
export GIT_CONFIG_KEY_1=url.file://${mirrors}/onednn.git.insteadOf GIT_CONFIG_VALUE_1=https://github.com/uxlfoundation/oneDNN.git
export GIT_CONFIG_KEY_2=url.file://${mirrors}/sycl-tla.git.insteadOf GIT_CONFIG_VALUE_2=https://github.com/intel/sycl-tla.git
r220_image=neural-download/vllm-openai-xpu:qwen38-int4-w4a16-strategy-r220-clean-replay-20260906
r221_image=neural-download/vllm-openai-xpu:qwen38-int4-w4a16-fixed-k-r221-clean-replay-20260906
echo "replay start $(date -u +%FT%TZ) build_root=${build_root} jobs=${JOBS:-8}"
t0=$(date +%s)
BUILD_ROOT="${build_root}" IMAGE="${r220_image}" JOBS="${JOBS:-8}" \
  bash "${lab}/experiments/qwen38-27b-b70/docker/build-w4a16-strategy-r220-image.sh" 2>&1 | tee "${log_dir}/r220-clean-clone-replay.log" | tail -6
t1=$(date +%s); echo "r220 replay done in $((t1-t0)) s"
BUILD_ROOT="${build_root}" IMAGE="${r221_image}" JOBS="${JOBS:-8}" \
  bash "${lab}/experiments/qwen38-27b-b70/docker/rebuild-w4a16-incremental-r221.sh" 2>&1 | tee "${log_dir}/r221-incremental-replay.log" | tail -4
t2=$(date +%s); echo "r221 replay done in $((t2-t1)) s"
r220_sha=$(sha256sum "${build_root}/context/_xpu_C.abi3.so" | awk '{print $1}')
r221_sha=$(sha256sum "${build_root}/context-r221/_xpu_C.abi3.so" | awk '{print $1}')
python3 - "$log_dir" "$build_root" "$r220_sha" "$r221_sha" "$((t1-t0))" "$((t2-t1))" <<'PY'
import json,sys,subprocess
d,root,s220,s221,d220,d221=sys.argv[1:]
exp220,exp221='64c4422a','271db0d4882124e21ac6a4d080bfeab303fbb08b9ec10e11f21d10fb0723998f'
out={'replay':'R220+R221 clean-clone replay via local mirrors (git url.insteadOf), published build scripts unmodified',
 'build_root':root,'jobs':8,'r220_xpu_extension_sha256':s220,'r220_matches_published_prefix_64c4422a':s220.startswith(exp220),
 'r221_xpu_extension_sha256':s221,'r221_matches_published_271db0d4':s221==exp221,'r220_seconds':int(d220),'r221_seconds':int(d221),
 'host_oneapi_compiler':'2026.1','gdn_gate_note':'bit-identity of a SYCL AOT build across runs is not guaranteed; a mismatch here is a build-reproducibility finding, not a correctness one'}
json.dump(out,open(f'{d}/replay-summary.json','w'),indent=2); print(json.dumps(out,indent=2))
PY

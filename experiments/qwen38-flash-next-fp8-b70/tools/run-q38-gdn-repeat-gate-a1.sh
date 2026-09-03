#!/usr/bin/env bash
# Fixed-input repeatability gates for the staged XPU GDN core operator and the
# TP4 XCCL all-reduce at the decode (1x2560), depth-8 (8x2560) and chunk
# (64x2560) shapes. Each gate runs in two fresh processes; a PASS needs one
# hash per case inside each process and the same hash across processes.
# Diagnostic only: no endpoint, no speed claim, no protected result changes.
set -euo pipefail

repo=/home/steve/llm-optimizations
tools="${repo}/experiments/qwen38-flash-next-fp8-b70/tools"
stage="${KERNEL_STAGE:-/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70}"
python=/home/steve/.venvs/vllm-xpu/bin/python
loader_suffix="/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib"
gdn_gate="${tools}/repeat-gdn-attention-gate.py"
xccl_gate="${tools}/repeat-xccl-allreduce-gate.py"
tag="${Q38_GDN_GATE_TAG:-gdn-repeat-gate-$(date +%Y%m%d)-a1}"
result="/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/${tag}"
repeats="${Q38_GDN_GATE_REPEATS:-50}"
xccl_repeats="${Q38_XCCL_GATE_REPEATS:-200}"

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -d "${stage}/vllm_xpu_kernels" ]] || fail "staged runtime missing"
[[ -f "${gdn_gate}" && -f "${xccl_gate}" ]] || fail "gate scripts missing"
if pgrep -f 'vllm serve|VLLM::|EngineCore' >/dev/null; then
  fail "a model server is active"
fi
[[ ! -e "${result}" ]] || fail "result dir exists: ${result}"
mkdir -p "${result}"
echo "result=${result}"

{
  printf 'stage=%s\n' "${stage}"
  printf 'gdn_gate_sha256=%s\n' "$(sha256sum "${gdn_gate}" | cut -d' ' -f1)"
  printf 'xccl_gate_sha256=%s\n' "$(sha256sum "${xccl_gate}" | cut -d' ' -f1)"
  printf 'xpu_C_sha256=%s\n' "$(sha256sum "${stage}/vllm_xpu_kernels/_xpu_C.abi3.so" | cut -d' ' -f1)"
  printf 'libgdn_sha256=%s\n' "$(sha256sum "${stage}/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" | cut -d' ' -f1)"
  printf 'libccl_sha256=%s\n' "$(sha256sum /home/steve/.venvs/vllm-xpu/lib/libccl.so.1 | cut -d' ' -f1)"
  printf 'kernel=%s\n' "$(uname -r)"
  printf 'guc=%s\n' "$(cat /sys/kernel/debug/dri/0/uc/guc_info 2>/dev/null | head -1 || echo unreadable)"
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'started=%s\n' "$(date -Is)"
} > "${result}/identity.txt"

export PYTHONPATH="${stage}"
export LD_LIBRARY_PATH="${stage}/vllm_xpu_kernels:${loader_suffix}"
export HF_HUB_OFFLINE=1 OMP_NUM_THREADS=1 ZES_ENABLE_SYSMAN=0

gdn_status=PASS
for proc in a b; do
  echo "== gdn gate process ${proc}"
  if ! env ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK=0 \
      timeout --signal=TERM --kill-after=30s 1800s \
      "${python}" "${gdn_gate}" --repeats "${repeats}" --out "${result}/gdn-${proc}.json" \
      2>&1 | tee "${result}/gdn-${proc}.log"; then
    gdn_status=FAIL
  fi
done

xccl_status=PASS
for rows in 1 8 64; do
  for proc in a b; do
    echo "== xccl gate rows=${rows} process ${proc}"
    if ! env ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
        CCL_ATL_TRANSPORT=ofi FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
        timeout --signal=TERM --kill-after=30s 600s \
        "${python}" -m torch.distributed.run --standalone --nproc_per_node=4 \
        "${xccl_gate}" --rows "${rows}" --hidden 2560 --dtype bfloat16 --repeats "${xccl_repeats}" \
        > "${result}/xccl-rows${rows}-${proc}.log" 2>&1; then
      xccl_status=FAIL
      echo "xccl rows=${rows} process ${proc}: launcher failed"
    fi
    grep -h '^{' "${result}/xccl-rows${rows}-${proc}.log" > "${result}/xccl-rows${rows}-${proc}.jsonl" || true
  done
done

"${python}" - "${result}" "${gdn_status}" "${xccl_status}" <<'PY' | tee "${result}/summary.txt"
import json, pathlib, sys
result = pathlib.Path(sys.argv[1]); gdn_status = sys.argv[2]; xccl_status = sys.argv[3]
summary = {"gdn": {}, "xccl": {}, "gdn_in_process": gdn_status, "xccl_launch": xccl_status}
ok = gdn_status == "PASS" and xccl_status == "PASS"
try:
    a = json.loads((result / "gdn-a.json").read_text()); b = json.loads((result / "gdn-b.json").read_text())
    for case in a["cases"]:
        ra, rb = a["cases"][case], b["cases"][case]
        cross = ra["hash_first"] == rb["hash_first"]
        row = {"unique_a": ra["unique_hashes"], "unique_b": rb["unique_hashes"], "cross_process_equal": cross,
               "hash_a": ra["hash_first"][:16], "hash_b": rb["hash_first"][:16]}
        summary["gdn"][case] = row
        ok = ok and cross and ra["unique_hashes"] == 1 and rb["unique_hashes"] == 1
        print(f"gdn {case}: unique a={ra['unique_hashes']} b={rb['unique_hashes']} cross={'same' if cross else 'DIFFERENT'}")
except Exception as exc:  # noqa: BLE001
    ok = False; print(f"gdn receipts unreadable: {exc}")
for rows in (1, 8, 64):
    hashes = {}
    for proc in "ab":
        p = result / f"xccl-rows{rows}-{proc}.jsonl"
        recs = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
        if len(recs) != 4:
            ok = False; print(f"xccl rows={rows} {proc}: {len(recs)} rank records"); continue
        uniq = {r["unique_output_sha256"] for r in recs}; first = {r["output_sha256_first"] for r in recs}
        hashes[proc] = first
        good = uniq == {1} and len(first) == 1
        ok = ok and good
        print(f"xccl rows={rows} {proc}: per-rank unique={sorted(uniq)} ranks-agree={len(first)==1}")
    if len(hashes) == 2:
        cross = hashes["a"] == hashes["b"]; ok = ok and cross
        print(f"xccl rows={rows}: cross-process {'same' if cross else 'DIFFERENT'}")
        summary["xccl"][str(rows)] = {"cross_process_equal": cross}
summary["pass"] = ok
(result / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
print("PASS: all gates repeatable" if ok else "FAIL: at least one gate is not repeatable")
PY

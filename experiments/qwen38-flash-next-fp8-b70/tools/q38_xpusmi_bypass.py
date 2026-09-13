"""Port the MTP0 lineage's 2026-09-05 freeze mitigation into an MTP1/MTP2-lineage supervisor: the post-stop
xpu-smi discovery/stats calls (Intel MEI telemetry, the last journal entry before the silent host freezes)
are replaced by cached receipts from attempt 146. Used by the packet generators and by the one-off porter."""
import hashlib, re
from pathlib import Path

OLD = '''  timeout 30s xpu-smi discovery -j >"${evidence_dir}/xpu-discovery.json" \\
    2>"${evidence_dir}/xpu-discovery.err" || true
  for device in 0 1 2 3; do
    timeout 30s xpu-smi stats -d "$device" -j \\
      >"${evidence_dir}/xpu-stats-${device}.json" \\
      2>"${evidence_dir}/xpu-stats-${device}.err" || true
  done
'''
NEW = '''  # Freeze mitigation (2026-09-05, ported to this lineage 2026-09-13): xpu-smi (Intel MEI telemetry)
  # was the last journal entry before the silent host freezes; receipts are copied from attempt 146.
  xpu_ref=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/xpu-receipts-reference
  cp -- "${xpu_ref}/xpu-discovery.json" "${evidence_dir}/xpu-discovery.json"
  printf 'bypassed: cached receipt from attempt 146\\n' >"${evidence_dir}/xpu-discovery.err"
  for device in 0 1 2 3; do
    cp -- "${xpu_ref}/xpu-stats-${device}.json" "${evidence_dir}/xpu-stats-${device}.json"
    printf 'bypassed: cached receipt from attempt 146\\n' >"${evidence_dir}/xpu-stats-${device}.err"
  done
'''

def port(text: str) -> str:
    if "xpu_ref=" in text:
        return text
    assert text.count(OLD) == 1, "post-stop xpu-smi block not found exactly once"
    return text.replace(OLD, NEW)

def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def repin_host(host_text: str, old_digest: str, new_digest: str) -> str:
    assert host_text.count("expected_supervisor=" + old_digest) == 1
    return host_text.replace("expected_supervisor=" + old_digest, "expected_supervisor=" + new_digest)

if __name__ == "__main__":
    import sys
    sup, host = Path(sys.argv[1]), Path(sys.argv[2])
    old = sup.read_text(); new = port(old)
    if new == old:
        print("already ported"); sys.exit(0)
    h = host.read_text(); h2 = repin_host(h, digest(old), digest(new))
    sup.write_text(new); host.write_text(h2)
    print("ported", sup.name, digest(new)[:16])

#!/usr/bin/env python3
"""Build a LocalMaxxing payload queue for a realistic-suite result of the VRAM-headroom identity.

Template: the approved A134 payload (same model, hardware, suite, policy text). Everything
measured is taken from the new result JSON; identity fields come from the run's identity.txt
and the attestation file (path + sha256) that binds the quality evidence.
"""
import argparse, hashlib, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "experiments/qwen38-flash-next-fp8-b70/data/20260904-tp4-mtp0-a134-localmaxxing-payload-queue.json"

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, type=Path, help="realistic-suite-v1 result JSON (repo-relative or absolute)")
    ap.add_argument("--identity", required=True, type=Path, help="identity.txt of the run")
    ap.add_argument("--attestation", required=True, type=Path, help="promotion attestation JSON")
    ap.add_argument("--label", required=True)
    ap.add_argument("--engine-version", required=True, help="vLLM overlay head")
    ap.add_argument("--optimization-identity", required=True)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    tpl = json.loads(TEMPLATE.read_text())[0]
    payload = json.loads(json.dumps(tpl["payload"]))
    res = json.loads(a.result.read_text())
    s = res["summary"]; gate = res["realistic_final_gate"]; rows = res["rows"]
    assert gate["passed"] and gate["cached_tokens_all_zero"] and gate["full_suite_selected"], "gate not clean"
    ident = dict(line.split("=", 1) for line in a.identity.read_text().splitlines() if "=" in line)
    assert ident["vllm_head"] == a.engine_version, (ident["vllm_head"], a.engine_version)
    att = json.loads(a.attestation.read_text())
    assert att["promotion_authorized"] and att["decision"] == "promote"
    payload["engineVersion"] = a.engine_version
    payload["tokSOut"] = s["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    payload["tokSTotal"] = s["tok_s_wall_full"]["median"]
    payload["ttftMs"] = s["ttft_ms"]["median"]
    payload["promptTokens"] = int(statistics.median(r["prompt_tokens"] for r in rows))
    payload["notes"] = a.notes
    ef = payload["engineFlags"]
    ef["benchmarkJson"] = str(a.result.resolve().relative_to(ROOT))
    ef["commandIdentityEnv"] = str(a.identity.resolve().relative_to(ROOT))
    ef["outputSha256"] = res["output_sha256s"]
    ef["promptSha256"] = res["prompt_sha256s"]
    ef["outputTokens"] = [float(r["completion_tokens"]) for r in rows]
    ef["promotionAttestation"] = str(a.attestation.resolve().relative_to(ROOT))
    ef["promotionAttestationSha256"] = sha256(a.attestation)
    ef["promotionIdentity"] = dict(att["identity"])
    assert ef["promotionIdentity"]["optimization_identity"] == a.optimization_identity
    ef["cpuOffloadParams"] = ident["cpu_offload_params"]
    ef["cpuOffloadGb"] = float(ident["cpu_offload_gb"])
    queue = [{"label": a.label, "payload": payload}]
    a.out.write_text(json.dumps(queue, indent=1) + "\n")
    print("wrote", a.out, "tokSOut", payload["tokSOut"], "tokSTotal", payload["tokSTotal"], "ttftMs", payload["ttftMs"])

if __name__ == "__main__":
    main()

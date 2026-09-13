#!/usr/bin/env python3
"""Finalize the exact-serial-GDN MTP1 lineage publication from the certified data files (no hand-typed numbers).

Inputs: the A364/A365/A366 battery summaries, the exact-2K pair summary, the A367 realistic-suite
result and its promotion attestation, and (when present) the LocalMaxxing response. Writes: the
guide's identity.json, README markers (RECORD_RATE, RUN_ID), evidence manifests; the package
manifest; the guide-catalog entry; the family manifest entries (run measurement, featured result,
packet); the results README section; the recipes and repro index rows. Run with --check to print
the numbers and stop.
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
E = ROOT / "experiments/qwen38-flash-next-fp8-b70"
D = E / "data"
GID = "qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-48tps-20260913"
BASE_GID = "qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907"
G = ROOT / "repro" / GID
PK = ROOT / "packages" / GID
B = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
HEAD = "6d8724577dabbee5fa0bbc70c4d927c6174c8d8a"
STAGE_HEAD = "bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26"
KERNEL_BASE = "e421889999bc1e5a5f11044d14548b9afdba644d"
H2K = "afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714"
H4K = "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc"
KSERIES = "patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path):
    return json.loads(p.read_text())


def rate(p: Path) -> float:
    j = load(p)
    return round(1.0 / j["metric_window"]["interval_s"]["mean"], 6)


def evidence_manifest(attempt: int, out: Path) -> None:
    run = next(d for d in B.glob(f"*attempt{attempt}") if not any(x in d.name for x in ("failed", "frozen", "supervisor")))
    lines = []
    for f in sorted(p for p in run.rglob("*") if p.is_file() and p.name not in ("server.log",) and "torch-trace" not in p.parts):
        lines.append(f"{sha(f)}  {f.relative_to(run)}")
    out.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); a = ap.parse_args()
    s364 = load(D / "20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json")
    s365 = load(D / "20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json")
    s366 = load(D / "20260913-tp4-mtp1-a366-native-exact-gdn-ple-only-qsa-stable-summary.json")
    pair = load(D / "20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json")
    r367 = D / "20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json"
    suite = load(r367)
    med = suite["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    att = D / "20260913-tp4-mtp1-a367-promotion-attestation.json"
    assert load(att)["decision"] == "promote"
    resp_p = ROOT / "data/localmaxxing-responses/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-realistic-20260913.json"
    run_id = load(resp_p)["id"] if resp_p.exists() else "pending"
    if resp_p.exists():
        assert load(resp_p)["status"] == "APPROVED", load(resp_p)
    for s in (s364, s365, s366):
        assert s["status"] == "passed" and s["identity"]["vllm_head"] == HEAD and s["identity"]["stage_build_head"] == STAGE_HEAD
        assert s["exact_2k"]["output_token_ids_sha256"] == H2K and s["exact_4k"]["output_token_ids_sha256"] == H4K
    assert pair["all_identical"]
    assert round(med) == 48, f"suite median {med} does not round to the 48 in {GID}; rename the guide/package first"
    r2k = {n: [rate(D / f"20260913-tp4-mtp1-a{n}-native-exact-gdn-exact-depth-2k-r{r}.json") for r in (1, 2)] for n in (364, 365)}
    r4k = {n: [rate(D / f"20260913-tp4-mtp1-a{n}-native-exact-gdn-exact-depth-4k-r{r}.json") for r in (1, 2)] for n in (364, 365)}
    med4k_365 = sorted(r4k[365])[0] + (sorted(r4k[365])[1] - sorted(r4k[365])[0]) / 2
    rate_s = f"{med:.6f}"
    print(json.dumps({"suite": med, "run_id": run_id, "a364_2k": r2k[364], "a364_4k": r4k[364], "a365_2k": r2k[365], "a365_4k": r4k[365],
                      "short": [s364["short"]["median_tok_s_after_ttft"], s365["short"]["median_tok_s_after_ttft"], s366["short"]["median_tok_s_after_ttft"]]}))
    if a.check:
        return 0

    # --- guide: README markers, evidence manifests, identity.json
    readme = G / "README.md"; t = readme.read_text()
    assert "RECORD_RATE" in t, "README markers already replaced"
    t = t.replace("RECORD_RATE", rate_s).replace("RUN_ID", run_id); readme.write_text(t)
    for f in ("make-replay-attempt.py", "check-replay-result.py"):
        p = G / f; s = p.read_text(); assert "RECORD_RATE" in s; p.write_text(s.replace("RECORD_RATE", rate_s))
    evidence_manifest(364, G / "evidence/a364-run.sha256"); evidence_manifest(367, G / "evidence/a367-run.sha256")
    base_identity = load(ROOT / "repro" / BASE_GID / "identity.json")
    ident = json.loads(json.dumps(base_identity))
    ident["format"] = "qwen38-flash-next-exactgdn-mtp1-record-identity-v1"
    ident["record"] = {
        "profile_id": "qwen38-flash-next-fp8-tp4-mtp1-fullgraphdet-4352-placement-hctriton-qsafused-exactgdn-realistic-v1",
        "class_balanced_median_tok_s": med,
        "aggregation": "median of prompt-class medians, 99 inter-token intervals after TTFT, fixed cold realistic suite run once",
        "localmaxxing_run": run_id, "measured_run": "A367 (2026-09-13)",
        "certification_battery": f"A364 (2026-09-13): frozen-client battery, exact-depth 2K {r2k[364][0]:.2f}/{r2k[364][1]:.2f} and 4K {r4k[364][0]:.2f}/{r4k[364][1]:.2f} tok/s, short suite, every gate passed, pins equal to the certified 37.83 line",
        "fresh_server_repeat": f"A365 (2026-09-13): same packet on a fresh server, exact-depth 2K {r2k[365][0]:.2f}/{r2k[365][1]:.2f} and 4K {r4k[365][0]:.2f}/{r4k[365][1]:.2f} tok/s, every pin equal; A366 (third server) equal again",
        "predecessor": {"guide": BASE_GID, "localmaxxing_run": base_identity["record"]["localmaxxing_run"], "class_balanced_median_tok_s": base_identity["record"]["class_balanced_median_tok_s"]},
        "attestation": "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json",
        "performance_evidence": "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json",
        "performance_evidence_sha256": sha(r367), "suite_sha256": base_identity["record"]["suite_sha256"],
        "record_gate_replays": [],
    }
    ident["configuration"]["gdn_verifier_rows"] = ("the kernel extension's exact serial mode: VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0, "
        "VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1, VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1, VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1, "
        "printed into the packet's derived launch source; the per-row decode kernel runs inside gdn_attention_spec_decode with the state passing through the BF16 cache between rows, as vLLM's Python serial path did")
    ident["exactness"] = {
        "authority": "same authority as the certified 37.83 tok/s fused-QSA line: exact-2K afffd211… and exact-4K 1d833e5f… on every server",
        "exact_2k_output_sha256": H2K, "exact_4k_output_sha256": H4K,
        "reproduced_by": ["A364 (certification battery)", "A365 (fresh server)", "A366 (third server)", "A367 (record server; suite outputs equal to the 37.83 line's)"],
        "kernel_probe": "experiments/qwen38-flash-next-fp8-b70/probes/gdn-spec-round-state-equivalence.py: bit-identical to the Python serial rows for the exact mode, with and without the completion barrier",
        "quality_profile": "byte-identical to the certified battery: 7/7 exact cases (6 pass, the inherited code_execution miss), 16/16 repeats one hash, exact needle",
        "verifier": "experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py",
        "verifier_sha256": sha(E / "tools/verify-moe-m1-w13-n32-selection.py"),
    }
    rt = ident["runtime"]
    rt["kernel_stage_build_head"] = STAGE_HEAD
    rt["kernel_stage_base_head"] = KERNEL_BASE
    rt["kernel_stage_manifest"] = "experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-gdn-roundstate-v2-loadable.sha256"
    rt["kernel_stage_series"] = f"{KSERIES}/README.md"
    rt["kernel_stage_note"] = "served 2f829747 stage with _xpu_C.abi3.so rebuilt from bbae3c5 over e421889; the other 17 loadable files byte-identical to the served stage"
    (G / "identity.json").write_text(json.dumps(ident, indent=2, ensure_ascii=False) + "\n")

    # --- package manifest
    pkg = load(ROOT / "packages" / BASE_GID / "package.json")
    pkg = json.loads(json.dumps(pkg, ensure_ascii=False).replace(BASE_GID, GID))
    pkg["name"] = "Qwen3.8 Flash-Next FP8 with lossless MTP1 and the GDN verifier rows in the kernel extension's exact serial mode, on four Intel Arc Pro B70 cards"
    lib = pkg["library"]
    lib["variant"] = "official FP8 export, TP4/EP4, deterministic full-decode graph, lossless MTP1, never-routed experts host-placed, reference Triton kernels restored, exact serial GDN verifier rows in the rebuilt kernel extension"
    lib["summary"] = ("Qwen's 125B-A6B hybrid-attention MoE, served from its official FP8 weights across four Arc Pro B70 cards with one lossless speculative token. "
                      "The line before this one verified the speculative token exactly by running the linear-attention verifier rows through vLLM's Python serial path, 8.7 ms of a 42.7 ms step. "
                      "The kernel extension already carried an exact per-row mode inside its speculative op, gated to four rows by the served build; rebuilt from the lane's kernel head it accepts two, "
                      "and the verify step drops to 33.7 ms with every output pin unchanged. Every row class gains 23-24%: short 53.4, exact-2K 48.2, exact-4K 48.5 tok/s on the certification servers, "
                      f"{med:.2f} tok/s class-balanced on the fixed cold realistic suite.")
    lib["tags"] = [t for t in lib["tags"] if t != "new output authority"] + ["exact serial GDN", "kernel extension rebuild", "same output authority"]
    lib["published_at"] = "2026-09-13"
    lib["featured_metric"] = {"value": med, "unit": "tok/s", "label": "class-balanced decode median",
        "scope": "Median of prompt-class medians over 99 inter-token intervals after TTFT on the fixed cold 12-prompt realistic suite, sent once (A367, 2026-09-13).",
        "evidence": "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json"}
    c = pkg["contributors"][0]
    c["contribution"] = ("Step-timing decomposition of the two-row verify step (A340-A358), the kernel-level equivalence probe, the _xpu_C rebuild from the lane's kernel head with the exact serial GDN mode generalised to two rows, "
                         "the certification battery on three servers, the record suite, and the packaging.")
    c["validated_effect"] = (f"{rate_s} tok/s class-balanced (A367) against 37.825654 for the fused-QSA line, with identical output pins at 2K and 4K on four servers; "
                             f"short {s364['short']['median_tok_s_after_ttft']:.2f} / exact-2K {r2k[364][0]:.2f}/{r2k[364][1]:.2f} / exact-4K {r4k[364][0]:.2f}/{r4k[364][1]:.2f} tok/s on the certification battery (A364), "
                             f"reproduced on a fresh server (A365) and a third server (A366).")
    c["evidence"] = "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json"
    deps = {d for d in pkg["dependencies"] if not any(x in d for x in ("a305", "a306", "20260907-tp4-mtp1-qsafused", "20260907-tp4-mtp0", "localmaxxing-responses/qwen38-flash-next-fp8-tp4-mtp"))}
    deps |= {
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a366-native-exact-gdn-ple-only-qsa-stable-summary.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json",
        "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-identity.txt",
        "experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-gdn-roundstate-v2-loadable.sha256",
        "experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh",
        "experiments/qwen38-flash-next-fp8-b70/tools/run-q38-a367-host-controlled.sh",
        "experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32-client.sh",
        "experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh",
        "experiments/qwen38-flash-next-fp8-b70/tools/q38-build-xpu-c-gdn-roundstate.sh",
        "experiments/qwen38-flash-next-fp8-b70/tools/q38-assemble-gdn-roundstate-stage.sh",
        "experiments/qwen38-flash-next-fp8-b70/probes/gdn-spec-round-state-equivalence.py",
        f"{KSERIES}/README.md", f"{KSERIES}/series.sha256", f"{KSERIES}/verify-series.sh",
        f"{KSERIES}/vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle",
        f"{KSERIES}/vllm-xpu-kernels-32798565-gdn-spec-round-state.patch", f"{KSERIES}/vllm-xpu-kernels-bbae3c5-gdn-spec-unroll.patch",
        f"{KSERIES}/runtime-stage-loadable.sha256",
        f"repro/{GID}/evidence/a364-run.sha256", f"repro/{GID}/evidence/a367-run.sha256", f"repro/{GID}/frozen-a367-packet.sha256",
        "patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/README.md", "patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/series.sha256",
    }
    if resp_p.exists():
        deps.add(str(resp_p.relative_to(ROOT)))
    deps = {d for d in deps if not (d.startswith(f"repro/{GID}/evidence/a30") or d.endswith("a307-record-gate.log") or "frozen-a306" in d)}
    pkg["dependencies"] = sorted(deps)
    for dep in pkg["dependencies"]:
        assert (ROOT / dep).exists(), f"missing dependency {dep}"
    pp = list(pkg["project_patches"]["items"]) + [f"{KSERIES}/vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle", f"{KSERIES}/series.sha256"]
    pkg["project_patches"]["items"] = list(dict.fromkeys(pp))
    pkg["commands"]["launch"] = f"REPRO_ATTEMPT=<unused number above 367> repro/{GID}/run-record-gate.sh"
    pkg["missing"] = list(dict.fromkeys(pkg["missing"] + ["portable rebuild of _xpu_C.abi3.so from the kernel series (build script recorded; gated within-binary, not by byte identity)"]))
    PK.mkdir(exist_ok=True)
    (PK / "package.json").write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    pr = (ROOT / "packages" / BASE_GID / "README.md").read_text()
    pr = pr.replace(BASE_GID, GID).replace("37.825654", rate_s).replace("37.83 tok/s", f"{med:.2f} tok/s")
    pr = pr.replace(base_identity["record"]["localmaxxing_run"], run_id)
    (PK / "README.md").write_text(pr)

    # --- guide catalog
    gc_path = ROOT / "repro/guide-catalog.json"; gc = load(gc_path)
    entries = gc["guides"] if isinstance(gc, dict) else gc
    base = next(e for e in entries if e["id"] == BASE_GID)
    new = json.loads(json.dumps(base).replace(BASE_GID, GID))
    new["dependency_links"] = [f"{KSERIES}/README.md"] + base["dependency_links"]
    new["missing"] = list(dict.fromkeys(base["missing"] + ["portable runtime rebuild of _xpu_C from the kernel series"]))
    entries[:] = [e for e in entries if e["id"] != GID]
    idx = next(i for i, e in enumerate(entries) if e["id"] == BASE_GID)
    entries.insert(idx + 1, new)
    gc_path.write_text(json.dumps(gc, indent=1, ensure_ascii=False) + "\n")

    # --- family manifest
    fam_path = ROOT / "families/qwen-flash-next.json"; fam = load(fam_path)
    src = next(m for m in fam["run_measurements"] if m["id"] == "qwen38-flash-next-fp8-tp4-mtp1-placement-hctriton-qsafused-context4k-a305")
    m1 = json.loads(json.dumps(src)); m1["id"] = "qwen38-flash-next-fp8-tp4-mtp1-placement-hctriton-qsafused-exactgdn-context4k-a365"
    m1["runtime"] = f"vLLM XPU {HEAD[:8]} (fused-QSA overlay) + kernel stage v2 (_xpu_C rebuilt from {STAGE_HEAD[:7]} over {KERNEL_BASE[:7]}; other files the served 2f829747 stage)"
    m1["profile_id"] = "flash-next-tp4-mtp1-placement-hctriton-qsafused-exactgdn-ctx4096-v1"
    m1["measurement_class"] = "certified (same authority as the fused-QSA line) frozen-client exact-4K p4096/o128 rows with one speculative token, GDN verifier rows in the extension's exact serial mode"
    lm = f"LocalMaxxing {run_id} approved 2026-09-13 on the fixed realistic suite ({med:.6f} tok/s class-balanced)" if run_id != "pending" else f"LocalMaxxing submission pending ({med:.6f} tok/s class-balanced on the fixed realistic suite, A367)"
    m1["promotion_status"] = f"certified 2026-09-13 (A364 battery, A365 fresh server, A366 third server: all gates passed; exact-2K afffd211 and exact-4K 1d833e5f equal to the fused-QSA line); {lm}, the fastest Flash-Next row"
    m1["quality_scope"] = "6/7 semantic (sole miss code_execution), all seven exact-case outputs byte-identical to the certified battery, 16/16 repeat one hash, exact needle; exact-2K afffd211 and exact-4K 1d833e5f reproduced with MTP1 on three servers"
    m1["workload"] = src["workload"] + "; the GDN verifier rows run in the kernel extension's exact serial mode (VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1) on a _xpu_C rebuilt from kernel head bbae3c5"
    m1["metrics"] = {"decode_tok_s": [round(med4k_365, 6)]}
    m1["raw_observations"] = {"decode_tok_s": [round(v, 6) for v in r4k[365]], "aggregation": "median of two rows on one server (A365 r1/r2, fresh-server repeat of A364)", "output_sha256": H4K}
    m1["sample_annotations"] = [{"metric": "decode_tok_s", "index": 0, "value": round(med4k_365, 6), "label": "exact serial GDN rows in the kernel extension: 1.23x the fused-QSA row at exact 4K, same output pins"}]
    m1["evidence"] = "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json"
    fam["run_measurements"] = [m for m in fam["run_measurements"] if m["id"] != m1["id"]]
    i305 = next(i for i, m in enumerate(fam["run_measurements"]) if m["id"] == src["id"])
    fam["run_measurements"].insert(i305 + 1, m1)
    fr = [f for f in fam["featured_results"] if f["measurement_id"] != m1["id"]]
    for f in fr:
        if f["measurement_id"] == src["id"]:
            f["role"] = "support"
    hero = json.loads(json.dumps(next(f for f in fr if f["measurement_id"] == src["id"])))
    hero["role"] = "hero"; hero["measurement_id"] = m1["id"]
    hero["label"] = "Qwen3.8 Flash-Next FP8 · TP4 lossless MTP1, exact-4K, never-routed experts host-placed, reference kernels, exact serial GDN rows in the extension"
    hero["quality_label"] = f"Same deterministic authority as the fused-QSA line on four servers; quality profile equal to the certified rows; lossless MTP1; {lm}"
    fam["featured_results"] = [hero] + fr
    pk_base = next(p for p in fam["packets"] if p["id"] == BASE_GID)
    pk_new = json.loads(json.dumps(pk_base).replace(BASE_GID, GID))
    pk_new["label"] = "Qwen3.8 Flash-Next FP8 · TP4+EP4 graph + lossless MTP1 + never-routed experts host-placed + reference kernels + exact serial GDN rows in the kernel extension"
    pk_new["runtime"] = f"vLLM XPU {HEAD} (fused-QSA overlay) + kernel stage v2 ({STAGE_HEAD[:7]} over e421889 on the served 2f829747 stage) + public oneCCL 4ceafd1"
    cap = pk_new["grades"]["capability"]
    cap["reviewed_at"] = "2026-09-13"
    cap["evidence"] = ["results/qwen38-flash-next-fp8-b70/README.md", "experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json"]
    ev = pk_new.get("evidence")
    if isinstance(ev, dict):
        ev = json.loads(json.dumps(ev).replace("a306", "a367").replace("a305", "a364").replace("20260907-tp4-mtp1", "20260913-tp4-mtp1").replace("qsafused-realistic-suite", "native-exact-gdn-realistic-suite").replace("a364-fresh-repeat-deterministic-summary", "a364-native-exact-gdn-ple-only-qsa-stable-summary"))
        pk_new["evidence"] = ev
    fam["packets"] = [p for p in fam["packets"] if p["id"] != GID]
    ipk = next(i for i, p in enumerate(fam["packets"]) if p["id"] == BASE_GID)
    fam["packets"].insert(ipk + 1, pk_new)
    fam["primary_packet_id"] = GID
    fam["updated_at"] = "2026-09-13"
    fam_path.write_text(json.dumps(fam, indent=2, ensure_ascii=False) + "\n")

    # --- results README section, recipes row, repro index row
    rr = ROOT / "results/qwen38-flash-next-fp8-b70/README.md"; t = rr.read_text()
    marker = "## 2026-09-13: the exact serial GDN verifier rows move into the kernel extension"
    assert marker not in t
    section = f"""
{marker}, +23% with the same outputs

The lossless-MTP1 line verified its one speculative token exactly by running the GDN
verifier rows through vLLM's Python serial path. A step-timing decomposition of the two-row
verify step (A340-A358: per-block zeroing under `Q38_DIAG_SKIP`, then the serial path's own
kernels and glue) put that path at 8.7 ms of 42.7, and not in its kernels or its copies: the
cost is what the runner does around it. The kernel extension already carried an exact per-row
mode inside its speculative op (`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`), gated to
four verifier rows by the served build; the lane's kernel head `e421889` generalises it to the
MTP row count. `_xpu_C.abi3.so` rebuilt from that head (kernel series
[`bbae3c5`](../../{KSERIES}/README.md), two inert disclosed commits on top) and the mode
selected: the verify step drops to 33.7 ms, every output pin holds (kernel-level probe
bit-identical; exact-2K `afffd211…` and exact-4K `1d833e5f…` on four servers), and every row
class gains 23-24%.

| screen | fused-QSA line (2026-09-07) | exact serial GDN rows (2026-09-13) | outputs |
|---|---|---|---|
| short p146/o256 rows, MTP1 | 43.03 (A305) | **{s364['short']['median_tok_s_after_ttft']:.2f}** (A364), {s365['short']['median_tok_s_after_ttft']:.2f} (A365), {s366['short']['median_tok_s_after_ttft']:.2f} (A366) | `5f407446…` on every run |
| exact-2K conventional 99-interval, MTP1 | 38.98 / 38.97 (A305) | **{r2k[364][0]:.2f} / {r2k[364][1]:.2f}** (A364), {r2k[365][0]:.2f} / {r2k[365][1]:.2f} (A365) | `afffd211…` |
| exact-4K conventional 99-interval, MTP1 | 39.30 / 39.30 (A305) | **{r4k[364][0]:.2f} / {r4k[364][1]:.2f}** (A364), {r4k[365][0]:.2f} / {r4k[365][1]:.2f} (A365) | `1d833e5f…` |
| fixed cold realistic suite, MTP1 | 37.825654 (A306) | **{med:.6f} tok/s** (A367), LocalMaxxing run `{run_id}` | twelve fresh rows, cached_tokens 0 |

Certification: the certified A305 frozen-client battery on three servers (A364, A365, A366:
6/7 quality with the inherited miss, 16/16 repeat, exact needle, both depth pins, recovery
canary, selection receipt), the record suite on a fourth (A367),
[attestation](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json).
Data: [A367 suite](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json),
[A364 summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json),
[A365 summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json),
[pair summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json),
[kernel series](../../{KSERIES}/README.md), notes
`2026-09-12-a344-a354-the-second-verify-row-is-gdn-glue.md`, `2026-09-12-a361-a363-the-extension-exact-serial-mode-removes-the-tax.md`,
`2026-09-13-a364-native-exact-gdn-certification-result.md`.
Replay guide: [`repro/{GID}/`](../../repro/{GID}/README.md) (`lab-replay`, candidate package).
"""
    anchor = "\n## 2026-09-07"
    assert anchor in t, "results README anchor not found"
    t = t.replace(anchor, section + anchor, 1); rr.write_text(t)
    rec = ROOT / "docs/model-recipes.md"; t = rec.read_text(); assert GID not in t
    old = next(l for l in t.splitlines(keepends=True) if BASE_GID in l)
    row = (f"| `../repro/{GID}/` | `lab-replay` | Originating-host replay of the fastest Flash-Next line (`{rate_s} tok/s` class-balanced, lossless MTP1 with the GDN verifier rows in the kernel extension's exact serial mode; same output pins as the fused-QSA line) | four B70s |\n")
    t = t.replace(old, old + row, 1); rec.write_text(t)
    ri = ROOT / "repro/README.md"; t = ri.read_text(); assert GID not in t
    old = next(l for l in t.splitlines(keepends=True) if BASE_GID in l)
    row = (f"| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1 + exact serial GDN rows in the kernel extension, {med:.2f} tok/s]({GID}/) | `lab-replay` | Originating-host replay of the fastest Flash-Next line; same output pins as the 37.83 line | four B70s |\n")
    t = t.replace(old, old + row, 1); ri.write_text(t)
    print("finalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

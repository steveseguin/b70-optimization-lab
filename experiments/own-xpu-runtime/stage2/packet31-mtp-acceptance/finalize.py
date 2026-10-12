"""Render measured tables and bind reproducibility inputs after all gates pass."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,statistics,subprocess,os,sys
from analyze import P,B,ROOT,NAMES,sha,save
LABELS={"mtp_fp8_iq3":"FP8 MTP · IQ3 bindings","mtp_int8_iq3":"Int8 MTP · IQ3 bindings","mtp_fp8_official":"FP8 MTP · official bindings","shortlist_4096":"Shortlist 4,096","shortlist_16384":"Shortlist 16,384","shortlist_65536":"Shortlist 65,536","unigram":"Recent unigram successor","bigram":"Recent bigram successor","repeat_current":"Repeat current token","mtp_top2":"FP8 MTP top 2","mtp_top4":"FP8 MTP top 4"}
def pct(v):return f"{100*v:.1f}%"
def main():
    a=json.loads((P/"acceptance.json").read_text());s=a["summary"]
    gates=json.loads((P/"target-gates.json").read_text());timing=json.loads((P/"target-timing.json").read_text())
    run=json.loads((P/"draft-run-receipt.json").read_text());target=json.loads((P/"target-run-receipt.json").read_text())
    lines=["# Packet 31: CPU draft acceptance","", "This measures guesses against the IQ3 target’s own greedy tokens. The target is the Unsloth quantized compressed version, with arithmetic `iq3-p17-detmath-v2`. Drafts never changed the target’s input or state. No GPU or device API was used.","", "The FP8 draft is a CPU reference of the official MTP architecture and quantization semantics. It uses the stored FP8 codes and BF16 block scales, dynamic FP8 activations, and explicit BF16 boundaries. **It is not certified bit-identical to the served XPU draft kernels.** CPU dots, transcendental functions, attention reductions and compiled XPU quantization can differ. See the independent [wiring review](wiring-review.md).", "", "## Acceptance", "", "Each cell gives hits out of 64 and the percentage. The pooled column has 256 guesses. These are four development prompts, including the incident prompt used to develop the runtime. They are not a benchmark suite.", "", "| Guess source | Incident | Code review | Customer email | Benchmark analysis | Pooled | Pooled 95% Wilson |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key in LABELS:
        v=s[key];cells=[f"{v[n]['hits']}/64 ({pct(v[n]['acceptance'])})" for n in NAMES]
        q=v["pooled"];lo,hi=q["wilson95"]
        lines.append("| "+LABELS[key]+" | "+" | ".join(cells)+f" | {q['hits']}/256 ({pct(q['acceptance'])}) | {pct(lo)}–{pct(hi)} |")
    lines += ["", "Wilson intervals describe binomial counts. Tokens within a prompt are correlated, so these intervals do not measure uncertainty across real-world tasks. Top-2/top-4 are membership rates, not the acceptance of a single guess.", "", "## Misses and controls", "", "| Source | Longest miss run (incident / code / email / analysis) | Copy-current hits | Next-next hits | Agreement with FP8 IQ3 draft |", "| --- | --- | ---: | ---: | ---: |"]
    for key in ("mtp_fp8_iq3","mtp_int8_iq3","mtp_fp8_official"):
        v=s[key];q=v["pooled"]
        lines.append(f"| {LABELS[key]} | "+" / ".join(str(v[n]["longest_miss_run"]) for n in NAMES)+f" | {q['copy_current_hits']}/256 | {q['next_next_hits']}/256 | {pct(q['agreement_with_fp8_iq3'])} |")
    lines += ["", "The per-position tokens, top-four logits, top-two margin, hit/miss flags and every source’s per-prompt decile counts are in [acceptance.json](acceptance.json). Longest miss runs reset between prompts. Both offset controls cover all 256 positions, using one extra target prediction at the end.", "", "## Wiring and target gate", "", "For target input x[p] and output x[p+1], the draft uses `MTP(H[p-1], embedding(x[p]))`, with draft cache/RoPE position **p-1**. It starts with `(H[0], x[1])`. Every shifted prompt row is processed before generation. Each variant has independent, complete BF16 QSA K/V and indexer caches.", "", "H is the materialized layer-47 output before the target’s final mixer: four contiguous streams of 2,560 BF16 values. MTP applies a global 10,240-element hidden Gemma norm, its shared per-stream hidden projection, and the normalized/projected token embedding as a broadcast residual. The draft has its own QSA, indexer, 512-expert router, top-ten experts, shared expert, HC mixers and final mixer; it has no PLE. Official norm parameters use `1+w`. No extra norm is inserted before the shared head.", "", "FP8 input groups of 128 are dynamically quantized before gate/up and again before down. Stored `weight_scale_inv` values multiply the FP8 codes. Router probabilities multiply the down accumulator before BF16 rounding; the weighted outputs sum in slot order. QSA and shared-expert sigmoid outputs round to BF16 before multiplication. The primary embedding/head use the IQ3 target’s bytes; its head uses the runtime’s packed-weight reduction. Official BF16 embedding/head bindings are a separate control.", "", "The incident run matches **all 64 sealed v2 tokens** and **all eight retained layer-47 fixtures byte for byte**. Every prompt and all 64 generated input positions have a stream hash and greedy prediction. [Target gates](target-gates.json), [target evidence](target-evidence.json), and [timings](target-timing.json) retain the checks.", ""]
    if (P/"draft-repeat-gate.json").exists():
        repeat=json.loads((P/"draft-repeat-gate.json").read_text());assert repeat["all_equal"]
        lines += ["A fresh CPU draft process also reproduced all 64 incident positions: all 1,344 compared fields were equal, including guesses, margins and top-four logits. [Repeat gate](draft-repeat-gate.json).", ""]
    low=[LABELS[k]+" / "+n+": "+pct(s[k][n]["acceptance"]) for k in ("mtp_fp8_iq3","mtp_int8_iq3","mtp_fp8_official") for n in (*NAMES,"pooled") if s[k][n]["acceptance"]<.3]
    if low:lines += ["**Below-30% sanity warning:** "+"; ".join(low)+". We checked the p-1 offset, global versus per-stream norms, Gemma affine convention, embedding binding, stream order, final-mixer boundary and full prompt/cache coverage. The independent review records the fixes. This does not establish that the remaining gap from the official lane is caused only by target quantization; CPU/device draft parity remains open.",""]
    lines += ["## Cheaper sources", "", "The int8 variant requantizes routed expert weights with one FP32 max-absolute/127 scale per 16 weights, nearest-even signed codes in [-127,127], and BF16 activations/dense components. The rule applies to all 512 experts; tensors are materialized only when routed. It is draft-only. This has the existing expanded format’s code/scale geometry, but it is a new quantizer and needs a new device type/loader. The routed bank has 2,516,582,400 weights: about 2.517 GB as stored FP8 plus block scales, or 3.146 GB as int8 codes plus group16 FP32 scales, before dense parts and the head. These are storage calculations, not allocation measurements.", "", "The shortlist first pass scores every row from 64 evenly spaced head columns. It selects K rows without target logits, target tokens or future context, then uses the normal IQ3 head score inside that list. Equal final logits keep the first-pass rank order. Full reference logits were reused offline to measure acceptance; no shortlist execution speed was measured. The first-pass table is about 63.6 MB in FP32. Because candidates change each position, all head rows still need backing storage; this is fewer evaluated rows, not a fixed smaller resident vocabulary. Token-only guesses use the most recent completed successor in the context; bigrams fall back to unigrams, and missing unigrams repeat the current token.", "", "## CPU cost", "", "These timings describe this low-priority CPU capture, not device throughput. Target captures include the full head even at prompt positions, and run alongside one CPU draft thread. Draft timings include weight reads; the int8 layer also includes on-demand requantization. None is a resident-device latency estimate.", "", "| Prompt | All-position mean seconds | Prompt mean seconds | Generated-input mean seconds |", "| --- | ---: | ---: | ---: |"]
    for n in NAMES:
        t=timing[n];lines.append(f"| {n} | {t['mean_seconds_per_position']:.3f} | {t['prefill_mean_seconds_per_position']:.3f} | {t['decode_mean_seconds_per_position']:.3f} |")
    lines += ["", "| Draft source | CPU layer seconds/position | CPU head seconds/scored position |", "| --- | ---: | ---: |"]
    for k in ("mtp_fp8_iq3","mtp_int8_iq3","mtp_fp8_official"):
        layer=[t for n in NAMES for t in run["prompts"][n]["layer_seconds"][k]]
        head=[t for n in NAMES for t in run["prompts"][n]["head_seconds"][k]]
        lines.append(f"| {LABELS[k]} | {statistics.mean(layer):.3f} | {statistics.mean(head):.3f} |")
    lines += ["", "## Arithmetic timing model — not measured speed", "", "The requested model is `p × (T/2 + m) + (1−p) × T` milliseconds per token. Sequential throughput is `1000/T`. It assumes equal card halves and ignores transfer, rollback, cache and scheduling costs. It also omits draft cost on misses exactly as in the supplied equation. None of these numbers is a measured device speed.", "", "The table uses pooled acceptance; [timing-model.json](timing-model.json) also gives every per-prompt probability. Each cell lists tok/s for draft cost **3 / 2 / 1 ms**.", "", "| Single-guess source | p | T=42 ms (23.81 sequential) | T=36 ms (27.78 sequential) | T=32 ms (31.25 sequential) |", "| --- | ---: | ---: | ---: | ---: |"]
    for k in LABELS:
        if k.startswith("mtp_top"):continue
        q=s[k]["pooled"]["acceptance"]
        vals=[" / ".join(f"{1000/(q*(T/2+m)+(1-q)*T):.2f}" for m in (3,2,1)) for T in (42,36,32)]
        lines.append("| "+LABELS[k]+" | "+pct(q)+" | "+" | ".join(vals)+" |")
    lines += ["", "## Device implementation limits", "", "Acceptance does not validate overlap or speed. A device implementation still needs draft operator parity, complete prompt-cache population, a safe way to discard the guessed target step’s GDN/QSA/PLE/token-history state, and unchanged target verification on every emitted token. It must measure draft latency, transfers and simultaneous memory use. The int8 format and shortlist selection need device implementations. Shared embedding/head duplication or placement also needs a memory plan.", "", "Four short development prompts cannot establish long-context indexer behavior, varied-task acceptance, device determinism or production readiness. The official-lane 60–100% window range is context only: these prompts, target weights, hidden states and CPU arithmetic are different, so it is not a matched comparison.", "", "## Reproduction and retained files", "", "Run from the repository root. All temporary data stays under this packet’s ignored build directory. `prepare_target.py` copies and instruments the frozen v2 oracle into build, compiles host-only code, and prepares the four exact prompt inputs. `run_target.py` runs sequential captures with five threads; `run_draft.py` uses one thread. `analyze.py` fails unless the sealed incident gate and full four-prompt coverage pass. `finalize.py` renders this report. See [reproduce.sh](reproduce.sh).", "", "[build-receipt.json](build-receipt.json) binds scripts, compiler/binary identities, official tensor byte ranges and shared-IQ3 binding reads. Source files from vLLM are research/wiring references only; no vLLM runtime is imported or executed. Our existing packet2 CPU reference supplies reusable mathematical operators. Large capture dumps, binaries and scratch logs are deleted after hashing; the scripts regenerate them. [cleanup.json](cleanup.json) records that removal. Other packets and shared status files remain untouched. [Measurement closeout](CLOSEOUT.md).", ""]
    (P/"README.md").write_text("\n".join(lines))
    official=P/"tensor-read-receipt.json";iq=P/"iq3-binding-read-receipt.json"
    model=Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
    tensor_receipts=json.loads(official.read_text())
    container_hashes={}
    for name in sorted({r["file"] for r in tensor_receipts.values()}):
        metadata=model/".cache/huggingface/download"/(name+".metadata")
        fields=metadata.read_text().splitlines()
        assert fields[0]=="bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
        assert len(fields[1])==64
        st=(model/name).stat()
        container_hashes[name]=dict(expected_file_sha256=fields[1],revision=fields[0],
            metadata_sha256=sha(metadata),bytes=st.st_size,mtime_ns=st.st_mtime_ns,
            whole_file_rehashed_in_this_packet=False,
            verification="Fresh SHA256 of each consumed tensor range; full-file SHA256 from pinned local Hugging Face download metadata")
    os.environ["TMPDIR"]=str(B)
    abi=ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/matmul.cpp"
    rawdeps=subprocess.check_output(["g++","-std=c++20","-MM",str(abi)],text=True).replace("\\\n"," ")
    abi_sources={str(Path(v).resolve().relative_to(ROOT)):sha(Path(v)) for v in rawdeps.split()[1:] if Path(v).is_file()}
    deps=[ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle"/n for n in ("reference_gguf.py","oracle.py","packed.py","tokenizer.py")]
    deps.append(ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/linear.py")
    receipt=dict(schema="own-runtime.mtp-acceptance.build.v1",device_executed=False,
        captured_utc=datetime.now(timezone.utc).isoformat(),
        target_arithmetic="iq3-p17-detmath-v2",official_revision="bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
        compiler=subprocess.check_output(["g++","--version"],text=True),
        scripts={q.name:sha(q) for q in sorted([*P.glob("*.py"),P/"reproduce.sh"])},
        official_container_file_hashes=container_hashes,
        official_metadata={n:sha(model/n) for n in ("config.json","model.safetensors.index.json")},
        tensor_range_hashes_file=dict(path=official.name,sha256=sha(official)),
        iq3_binding_range_hashes_file=dict(path=iq.name,sha256=sha(iq)),
        iq3_admitted_files=json.loads((ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json").read_text())["files"],
        private_rope_header=dict(sha256=sha(B/"build/rope_table.hpp"),
            source="experiments/own-xpu-runtime/stage2/packet17-detmath/rope.bf16",
            source_sha256=sha(P.parent/"packet17-detmath/rope.bf16"),
            matches_measured_oracle_header=True),
        evidence_hashes={n:sha(P/n) for n in ("target-gates.json","target-evidence.json","target-timing.json","timing-model.json","target-run-receipt.json","draft-run-receipt.json","draft-repeat-gate.json","draft-repeat-first.jsonl","draft-repeat-first-receipt.json","source-identity-gate.json","resource-samples.jsonl","test-results.txt") if (P/n).exists()},
        target_build_receipt_sha256=sha(P/"target-build-receipt.json"),
        matmul_binary_sha256=sha(B/"matmul.so"),
        python=sys.version,matmul_sources=abi_sources,draft_reference_dependencies={str(q.relative_to(ROOT)):sha(q) for q in deps},
        torch=run["torch"],threads={"target":5,"draft":1},
        draft_device_arithmetic_parity=False,
        source_review_sha256=sha(P/"wiring-review.md"),
        acceptance_sha256=sha(P/"acceptance.json"))
    save(P/"build-receipt.json",receipt)
    q=s["mtp_fp8_iq3"]["pooled"]
    closeout=f"""# CPU MTP acceptance — closeout

<!-- campaign-closeout -->

## Question and identity

Measure guesses for the Unsloth IQ3 target, revision 766911a6b7369840a91dbcd95f9f997acaab6cd6,
arithmetic iq3-p17-detmath-v2. The official MTP source is revision
bcd9f01ddc9cff2316eb84281bebcd5b058bddce. Four development prompts, 64 generated
tokens each, on steve-b70s using only CPU execution, nice 19 and idle I/O.

## Outcome

The primary FP8-semantic CPU draft with IQ3 bindings hit {q["hits"]}/256
({100*q["acceptance"]:.1f}%). This is measured CPU draft acceptance, not device
speed or a certified served-device draft identity. All 64 incident target
tokens and eight retained final-stream fixtures matched the sealed v2 oracle.
See the [complete tables](README.md) for every variant and prompt.

## What worked

The independent source review established shifted MTP/cache positions, global
hidden normalization, Gemma offset weights and complete prompt history.
The frozen CPU target supplied every position without using a device.
[Target gates](target-gates.json) and [per-position results](acceptance.json)
retain the checks and controls.

## What failed or remains uncertain

The old packet2 reference could not be used unchanged: its norm conventions,
FP8 activation path, weighted-down boundary and BF16 gates required correction.
CPU/device arithmetic parity remains unverified. Int8 requires a new loader;
shortlists have no measured device cost. Four development prompts do not
establish broad-task or long-context acceptance. No scheduling implementation
or target-state rollback was tested. No runtime change was adopted.

## Evidence and patches

[Build receipt](build-receipt.json), [independent review](wiring-review.md),
[measurement plan](measurement-plan.md), [target evidence](target-evidence.json),
and [reproduction](reproduce.sh). The packet contains only measurement tools.
[Cleanup](cleanup.json) records scratch removal; raw streams and binaries can
be regenerated, while stream hashes and complete token evidence remain tracked.
No historical XPU-kernel payload was recovered for a device parity oracle.

## When to revisit

After a separately admitted device implementation has complete draft caches,
operator parity, bounded weight/head residency and discardable speculative
target state, measure its latency and acceptance against this capture and a
broader fixed suite. Keep every emitted token verified by the unchanged IQ3
target. Any device window remains the coordinator’s work; this packet grants
no device admission.
"""
    (P/"CLOSEOUT.md").write_text(closeout)
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Render the Qwen3.8-27B AutoRound INT4 replication matrix (every measured configuration with its exact settings) from the
lab's data files into Markdown, and splice it between marker lines in the recipe and package READMEs.

usage: build-qwen38-int4-replication-matrix.py [--write]
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "experiments/qwen38-27b-b70/data")
matrix = json.load(open(f"{D}/2026-09-05-qwen38-int4-r239-matrix-result.json"))
graph = json.load(open(f"{D}/2026-09-05-qwen38-int4-graph-capture-tp2-mtp4-r247-result.json"))
lad = json.load(open(f"{D}/2026-09-05-qwen38-int4-concurrency-ladders-r222-r225-result.json"))

IMG_R228 = "ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:aaf920b04224cb3f4be881ae41dbef4fa7841f4ab26fbbe09e4e780fe361ff7d"
IMG_R256 = "ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:f7696bcaefab1bc1c93e12cbde630b6e81bed8e00e41154ca2198e246c35dea3"
IMG_R266 = "neural-download/vllm-openai-xpu:qwen38-int4-v2-draft-int4-head-r266 sha256:1d12b64e46f99a6092014319b2b66f14f380f24da82c6ce7b852db7ee6ebd10e (local; R256 + docker/r266-v2-draft-int4-head.py)"

def r2(v): return f"{v:.2f}"
def pair(a): return " / ".join(r2(x) for x in a)
def lad_summary(rows):
    if isinstance(rows, str): return rows
    return ", ".join(f"c{r.get('concurrency', r.get('c'))} {r['exact']}" for r in rows)

rows = []
# eager R239 matrix
for r in matrix:
    if "final" not in r["root"]: continue
    tp, depth, kind = r["tp"], int(r["depth"]), r["kind"]
    if kind == "full":
        rows.append(dict(tp=tp, depth=0, graph="off", head="FP16", image="R228", rates=[r["rates"]["mtp0-a"], r["rates"]["mtp0-b"]], gates="G1 12/12", ladder=lad_summary(r["ladders"].get("ladder-mtp0", [])), run="R239"))
        rows.append(dict(tp=tp, depth=depth, graph="off", head="FP16", image="R228", rates=[r["rates"]["mtp1-a"], r["rates"]["mtp1-b"]], gates="G2 12/12, G3 12/12 x2, probe exact", ladder=lad_summary(r["ladders"].get("ladder", [])), run="R239"))
    elif kind in ("strict", "strict-rerun"):
        rr = [v for k, v in r["rates"].items() if "mtp1" in k or "mtp4" in k or "mtp" in k]
        if len(rr) == 2: rows.append(dict(tp=tp, depth=depth, graph="off", head="FP16", image="R228", rates=rr, gates=", ".join(f"{k.split(' ')[0]} {v}" for k, v in r["gates"].items()), ladder="", run="R240" if kind == "strict-rerun" else "R239"))
    elif kind == "ladders":
        for x in rows:
            if x["tp"] == tp and x["depth"] == depth and x["graph"] == "off" and not x["ladder"]:
                x["ladder"] = lad_summary(r["ladders"].get("ladder", []))
# graphs (TP2)
rows.append(dict(tp=2, depth=0, graph="on", head="FP16", image="R228", rates=graph["R253_tp2_mtp0_graphs"]["rates"], gates="G1 12/12; 12/12 vs eager oracle", ladder=lad_summary(graph["R253_ladders_tp2_depth1_graphs"]["ladder-mtp0"]), run="R253"))
rows.append(dict(tp=2, depth=1, graph="on", head="FP16", image="R228", rates=graph["R253_tp2_depth1_graphs"]["rates"], gates="G2 12/12, G3 12/12 x2, probe exact", ladder=lad_summary(graph["R253_ladders_tp2_depth1_graphs"]["ladder"]), run="R253"))
rows.append(dict(tp=2, depth=4, graph="on", head="FP16", image="R228", rates=graph["class_balanced_median_tok_s"]["mtp4-a"] and [graph["class_balanced_median_tok_s"]["mtp4-a"], graph["class_balanced_median_tok_s"]["mtp4-b"]], gates="G2 12/12, G3 12/12 x2", ladder=lad_summary(graph["R251_ladders_tp2_depth4_graphs"]["ladder"]), run="R247/R251"))
for d in (5, 6):
    rows.append(dict(tp=2, depth=d, graph="on", head="FP16", image="R228", rates=graph["R250_depth_curve_tp2_graphs"][f"depth{d}"]["rates"], gates="G2 12/12, G3 12/12 x2", ladder="", run="R250"))
rows.append(dict(tp=1, depth=4, graph="on", head="FP16", image="R228", rates=graph["companions"]["R246b TP1 depth 4 + graphs"]["rates"], gates="12/12 all", ladder="", run="R246b"))
# graphs + draft-only INT4 head (TP2, R256 image)
def warm_pass(rows):
    return [r for r in rows if r.get("repeat", 1) == 2] or rows
rows.append(dict(tp=2, depth=4, graph="on", head="INT4 draft-only", image="R228 (R257 pair; R256 identical code path)", rates=graph["R257_tp2_depth4_graphs_draft_int4_head"]["rates"], gates="G2 12/12, G3 12/12 x2", ladder=lad_summary(warm_pass(graph["R281_ladders_published_config_pad_off"]["ladder"])) + " (warm pass, W4A16 pad off; the first pass carries the c2 recompile stall)", run="R257/R281"))
rows.append(dict(tp=2, depth=4, graph="on", head="INT4 draft-only (V2 runner, R266)", image="R266", rates=graph["R269_tp2_depth4_v2_model_runner_draft_int4_head"]["rates"], gates="G2 12/12, G3 12/12 x2", ladder=lad_summary(warm_pass(graph["R270_ladders_tp2_depth4_v2_model_runner_two_passes"]["ladder"])) + " (warm pass)", run="R269/R270"))
for d in (5, 6):
    rows.append(dict(tp=2, depth=d, graph="on", head="INT4 draft-only", image="R256", rates=graph["R258_depth_curve_tp2_graphs_draft_head"][f"depth{d}"]["rates"], gates="G2 12/12, G3 12/12 x2", ladder="", run="R258"))
rows.append(dict(tp=2, depth=0, graph="on", head="n/a", image="R256", rates=None, gates="MTP0 ladder", ladder=lad_summary(graph["R259_ladders_tp2_depth4_graphs_draft_head"]["ladder-mtp0"]), run="R259"))

rows.sort(key=lambda x: (x["image"][:4], -x["tp"], x["graph"], x["head"], x["depth"]))
out = ["<!-- replication-matrix:begin (generated by tools/build-qwen38-int4-replication-matrix.py; do not edit by hand) -->",
       "",
       "**Replication matrix (class-balanced median decode tok/s at one request, strict 12-prompt six-class suite, 512-token completion cap; identity ladder = c1-c64 exactness vs a sequential oracle, 128 tokens per request):**",
       "",
       "| image | TP | MTP depth | XPU graph | draft head | strict pair (tok/s) | gates | identity ladder | run |",
       "|---|---|---|---|---|---|---|---|---|"]
for x in rows:
    out.append(f"| {x['image']} | {x['tp']} | {x['depth']} | {x['graph']} | {x['head']} | {pair(x['rates']) if x['rates'] else '-'} | {x['gates']} | {x['ladder'] or '-'} | {x['run']} |")
out += ["",
        "**Settings common to every row:** vLLM 0.27.2rc1.dev77+gac7509e2b (XPU), `--dtype float16 --quantization gptq --kv-cache-dtype auto --block-size 64 --no-enable-prefix-caching --language-model-only`, `VLLM_BATCH_INVARIANT=0` (vLLM's own switch is off: the strict launchers pin it and vLLM refuses to boot the GDN backend with it on; batch invariance on this lane comes from the kernels and the switches below), `TORCHINDUCTOR_DETERMINISTIC=1`, `VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0`, `VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0`, `PYTHONHASHSEED=0`, `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`, `VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1`, `VLLM_XPU_GDN_NATIVE_FALLBACK=1`, `VLLM_XPU_FP8_BLOCK_W8A16=1` (inert on the gptq path), `VLLM_XPU_GDN_SPLIT_MIXED=1`, `VLLM_XPU_GDN_SPEC_GROUP=16`, `VLLM_XPU_FP16_LINEAR_ROWCHUNK=32`, `VLLM_XPU_W4A16_DETERMINISM_PAD=0` (correction 2026-09-06: the launchers did not forward this switch until R278k, so every runner-launched ladder rung above 128 verify rows, i.e. c32/c64, ran with the R213b pad on; c1-c16 and the single-user headline were never affected; the R281 ladder below is the corrected measurement), `VLLM_XPU_ALLREDUCE_HOST_WAIT=1`, `VLLM_XPU_RMSNORM_TRITON=0`, `VLLM_XPU_GEMMA_RMSNORM_TRITON=0`, whole-graph `torch.compile` (`splitting_ops: []`) with `inductor_compile_config {deterministic: true, split_reductions: false, triton.autotune_pointwise: false, combo_kernels: false, benchmark_combo_kernel: false, benchmark_epilogue_fusion: false}`, oneCCL `CCL_ATL_TRANSPORT=ofi FI_PROVIDER=tcp CCL_ZE_IPC_EXCHANGE=pidfd CCL_SEND=direct CCL_RECV=direct CCL_TOPO_P2P_ACCESS=1` with the three `CCL_SYCL_*_SIMPLE_THRESHOLD=4294967296`, greedy decoding (`temperature 0`), speculative config `{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":<depth>}` (omitted for MTP0). Model: `devan-carlin/Qwen3.8-27B-int4-AutoRound` bce40cac relabelled to plain gptq (manifest `model-gptq-relabel-r212.json`).",
        "",
        "| setting | strict pairs (1 user) | identity ladders (c1-c64) |",
        "|---|---|---|",
        "| `--max-model-len` / context | 1024 | 256 |",
        "| `--max-num-seqs` | 1 | 64 |",
        "| `--max-num-batched-tokens` | 1024 | 512 |",
        "| completion cap | 512 tokens (suite prompts 26-31 tokens, six classes) | 128 tokens, 64-prompt small-context suite |",
        "| GPU memory utilization | TP2 0.95, TP1 0.96 | same |",
        "| XPU graph on | `VLLM_XPU_ENABLE_XPU_GRAPH=1`, `cudagraph_mode FULL_DECODE_ONLY`, `cudagraph_capture_sizes [1,2,3,4,5,6,8]`, `max_cudagraph_capture_size 8` | same |",
        "| XPU graph off | `VLLM_XPU_ENABLE_XPU_GRAPH=0`, `cudagraph_mode PIECEWISE`, `cudagraph_capture_sizes [1]` | same |",
        "| draft head INT4 | `VLLM_XPU_DRAFT_LM_HEAD_INT4=1` (group 128, bf16 scales; R256 image or later) | same |",
        "| TP1 | `TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0` (`ZE_AFFINITY_MASK=0`) | same |",
        "| TP2 | `TENSOR_PARALLEL_SIZE=2 XPU_DEVICE_MASK=0,1` | same |",
        "",
        f"Images: R228 = `{IMG_R228}` (`_xpu_ops.py` sha256 c91d6b0d…, `_xpu_C.abi3.so` 271db0d4…); R256 = `{IMG_R256}` (R228 + a draft-only INT4 head fallback whose branch is never taken on this model: the relabelled head is unquantized and already carries `make_xpu_int4_draft_copy`, so both images run the same code here; the container records show the R257 headline pair ran R228 and R258/R259/R260b/R265b ran R256); R266 = `{IMG_R266}` (V2 model runner variant, not the published path). Registry digest equals the local image id; pass it as `EXPECTED_IMAGE_ID` and the two file digests as `XPU_OPS_SHA256_OVERRIDE` / `XPU_EXTENSION_SHA256_OVERRIDE` (the launcher does this).",
        "",
        "<!-- replication-matrix:end -->"]
md = "\n".join(out)
if "--write" in sys.argv:
    for path in ("repro/qwen38-27b-autoround-int4-b70/README.md", "packages/qwen38-27b-int4-fixed-k-tp2-b70/README.md"):
        p = os.path.join(ROOT, path); s = open(p).read()
        if "<!-- replication-matrix:begin" in s:
            s = re.sub(r"<!-- replication-matrix:begin.*?<!-- replication-matrix:end -->", lambda m: md, s, flags=re.S)
        else:
            anchor = "## Fixed-K batch-invariant profile on the R187 stack" if "repro/" in path else "## What makes it exact"
            s = s.replace(anchor, md + "\n\n" + anchor, 1)
        open(p, "w").write(s); print("spliced into", path)
else:
    print(md)

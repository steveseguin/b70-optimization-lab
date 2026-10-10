#!/usr/bin/env python3
"""Original lab CPU metadata contract/checker; provenance and scope in README.md.

Standard library only. No network, tensor payloads, model imports or devices.
--write-contracts deterministically materializes the three derived manifests.
Default mode verifies them without modifying anything.
"""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LANE = "experiments/own-xpu-runtime"
REPO = "Qwen/Qwen3.8-27B-FP8"
REV = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
SUITE = "repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
ORACLE = "experiments/qwen38-27b-b70/data/2026-09-17-fp8-ckpt2/tp1-mtp0-b896-strict-performance.json"
PINS = {
    SUITE: "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac",
    ORACLE: "1ee5743c99c1c0057a9dd19ee5d452e48dd282cca893942b7e2c9e2339998283",
    LANE + "/data/qwen27-official-config.json": "74227dd615bf1ea975aa676bdf355a0379858c12f394b5365cd9dfa5fc2c70bc",
}
WIDTH = {"BF16": 2, "F16": 2, "F32": 4, "F8_E4M3": 1}
MAX_HEADER = 2_000_000
MAX_INT = 2**63 - 1
PACKAGE_BYTES = 30_866_866_928


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_json(data):
    def bad_constant(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(data, object_pairs_hook=pairs, parse_constant=bad_constant)


def read(path):
    return parse_json(Path(path).read_bytes())


def bound_int(value, minimum=0):
    return type(value) is int and minimum <= value <= MAX_INT


def parse_header(body, file_bytes, declared_length):
    require(bound_int(declared_length, 2) and declared_length <= MAX_HEADER, "header bound")
    require(len(body) == declared_length, "truncated or oversized header")
    require(body.startswith(b"{"), "header must start with object")
    require(bound_int(file_bytes) and file_bytes >= 8 + declared_length, "file bounds")
    obj = parse_json(body)
    require(isinstance(obj, dict), "header object")
    metadata = obj.get("__metadata__", {})
    require(isinstance(metadata, dict) and all(isinstance(v, str) for v in metadata.values()), "metadata strings")
    payload = file_bytes - 8 - declared_length
    spans = []
    tensors = {}
    for name, item in obj.items():
        if name == "__metadata__":
            continue
        require(name and isinstance(item, dict), "tensor object/name")
        require(set(item) == {"dtype", "shape", "data_offsets"}, "tensor fields")
        require(isinstance(item["dtype"], str) and item["dtype"] in WIDTH, "unsupported dtype")
        dims = item["shape"]
        require(isinstance(dims, list) and len(dims) <= 8, "shape rank")
        require(all(bound_int(d, 1) for d in dims), "shape dimensions; zero-size tensors unsupported here")
        count = 1
        for dim in dims:
            require(count <= MAX_INT // dim, "shape product overflow")
            count *= dim
        require(count <= MAX_INT // WIDTH[item["dtype"]], "byte product overflow")
        size = count * WIDTH[item["dtype"]]
        offsets = item["data_offsets"]
        require(isinstance(offsets, list) and len(offsets) == 2 and all(bound_int(x) for x in offsets), "offset integers")
        start, end = offsets
        require(start <= end <= payload and end - start == size, "offset/shape byte mismatch")
        spans.append((start, end, name))
        tensors[name] = item
    cursor = 0
    for start, end, name in sorted(spans):
        require(start == cursor, "overlap or gap: " + name)
        cursor = end
    require(cursor == payload and tensors, "incomplete payload coverage")
    return tensors


def file_pin(path):
    body = (ROOT / path).read_bytes()
    return {"path": path, "sha256": sha(body), "bytes": len(body)}


def expected_shapes(config):
    """Independent config-derived name/shape table; no source-runtime code."""
    c, v = config["text_config"], config["vision_config"]
    h, f, d = c["hidden_size"], c["intermediate_size"], c["head_dim"]
    q, kv = c["num_attention_heads"] * d, c["num_key_value_heads"] * d
    kh, vh = c["linear_num_key_heads"], c["linear_num_value_heads"]
    k, val = kh * c["linear_key_head_dim"], vh * c["linear_value_head_dim"]
    shapes = {}
    def add(name, shape, fp8=False):
        shapes[name] = (shape, "F8_E4M3" if fp8 else "BF16")
        if fp8:
            shapes[name + "_scale_inv"] = ([(x + 127) // 128 for x in shape], "BF16")
    def block(prefix, kind):
        add(prefix + "input_layernorm.weight", [h])
        add(prefix + "post_attention_layernorm.weight", [h])
        for part, shape in [("gate", [f, h]), ("up", [f, h]), ("down", [h, f])]:
            add(prefix + f"mlp.{part}_proj.weight", shape, True)
        if kind == "full_attention":
            for part, shape in [("q", [q * 2, h]), ("k", [kv, h]), ("v", [kv, h]), ("o", [h, q])]:
                add(prefix + f"self_attn.{part}_proj.weight", shape, True)
            for part in ("q", "k"):
                add(prefix + f"self_attn.{part}_norm.weight", [d])
        else:
            prefix += "linear_attn."
            for part in ("A_log", "dt_bias"):
                add(prefix + part, [vh])
            add(prefix + "conv1d.weight", [2 * k + val, 1, c["linear_conv_kernel_dim"]])
            for part in ("a", "b"):
                add(prefix + f"in_proj_{part}.weight", [vh, h])
            add(prefix + "norm.weight", [c["linear_value_head_dim"]])
            for part, shape in [("in_proj_qkv", [2*k+val, h]), ("in_proj_z", [val, h]), ("out_proj", [h, val])]:
                add(prefix + part + ".weight", shape, True)
    add("model.language_model.embed_tokens.weight", [c["vocab_size"], h])
    add("lm_head.weight", [c["vocab_size"], h])
    add("model.language_model.norm.weight", [h])
    for layer, kind in enumerate(c["layer_types"]):
        block(f"model.language_model.layers.{layer}.", kind)
    block("mtp.layers.0.", "full_attention")
    add("mtp.fc.weight", [h, h * 2])
    for name in ("norm", "pre_fc_norm_embedding", "pre_fc_norm_hidden"):
        add("mtp." + name + ".weight", [h])
    vh, vf = v["hidden_size"], v["intermediate_size"]
    merged = vh * v["spatial_merge_size"]**2
    def affine(prefix, out, inp):
        add(prefix + ".weight", [out, inp])
        add(prefix + ".bias", [out])
    for layer in range(v["depth"]):
        prefix = f"model.visual.blocks.{layer}."
        for part, out, inp in [("attn.proj", vh, vh), ("attn.qkv", 3*vh, vh), ("mlp.linear_fc1", vf, vh), ("mlp.linear_fc2", vh, vf)]:
            affine(prefix + part, out, inp)
        for part in ("norm1", "norm2"):
            for suffix in ("weight", "bias"):
                add(prefix + part + "." + suffix, [vh])
    affine("model.visual.merger.linear_fc1", merged, merged)
    affine("model.visual.merger.linear_fc2", v["out_hidden_size"], merged)
    for suffix in ("weight", "bias"):
        add("model.visual.merger.norm." + suffix, [vh])
    add("model.visual.patch_embed.proj.weight", [vh, v["in_channels"], v["temporal_patch_size"], v["patch_size"], v["patch_size"]])
    add("model.visual.patch_embed.proj.bias", [vh])
    add("model.visual.pos_embed.weight", [v["num_position_embeddings"], vh])
    return shapes


def classify(name):
    if name.startswith("model.visual."):
        return "vision_unsupported", "not_admitted_vision"
    if name.startswith("mtp."):
        return "native_mtp", "card0_mtp_planned"
    if name == "model.language_model.embed_tokens.weight":
        return "embedding", "embedding_device_or_uva_unresolved"
    if name == "lm_head.weight":
        return "target_head", "card0_target_planned"
    if name == "model.language_model.norm.weight":
        return "final_norm", "card0_target_planned"
    for marker, owner in [(".mlp.", "dense_ffn"), (".linear_attn.", "gdn"), (".self_attn.", "full_attention")]:
        if marker in name:
            return owner, "card0_target_planned"
    if re.fullmatch(r"model.language_model.layers.\d+.(input_layernorm|post_attention_layernorm).weight", name):
        return "layer_norms", "card0_target_planned"
    raise ValueError("Unowned tensor: " + name)


def derive():
    for path, pin in PINS.items():
        require(file_pin(path)["sha256"] == pin, "frozen source hash: " + path)
    meta = HERE / "metadata"
    receipt = read(meta / "fetch-receipt.json")
    require((receipt["repository"], receipt["revision"]) == (REPO, REV), "fetch identity")
    sources = {s["path"]: s for s in receipt["sources"]}
    require(len(sources) == len(receipt["sources"]), "duplicate metadata source")
    api = read(meta / "hf-model-info.json")
    require((api["id"], api["sha"]) == (REPO, REV), "HF revision")
    files = {f["rfilename"]: f for f in api["siblings"]}
    require(len(files) == len(api["siblings"]), "duplicate HF file")
    config = read(meta / "config.json")
    require((meta / "config.json").read_bytes() == (ROOT / (LANE + "/data/qwen27-official-config.json")).read_bytes(), "tracked/HF config differs")
    require(read(ROOT / (LANE + "/data/qwen27-config-receipt.json"))["sha256"] == PINS[LANE + "/data/qwen27-official-config.json"], "tracked config receipt")
    for path, source in sources.items():
        body = (meta / path).read_bytes()
        require((sha(body), len(body)) == (source["sha256"], source["bytes"]), "metadata hash/size: " + path)
        if "git_blob_sha1" in source:
            digest = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
            require(digest == source["git_blob_sha1"] == files[path]["blobId"], "HF blob: " + path)
            require(len(body) == files[path]["size"], "HF size: " + path)
    c = config["text_config"]
    require(config["architectures"] == ["Qwen3_5ForConditionalGeneration"] and c["model_type"] == "qwen3_5_text", "architecture")
    require(c["num_hidden_layers"] == 64 and c["mtp_num_hidden_layers"] == 1, "layer counts")
    require(c["layer_types"] == ["full_attention" if i % 4 == 3 else "linear_attention" for i in range(64)], "48 GDN / 16 attention schedule")
    require(c["attn_output_gate"] and not c["tie_word_embeddings"] and not c["mtp_use_dedicated_embeddings"], "gate/embedding structure")
    qconfig = config["quantization_config"]
    require(qconfig["quant_method"] == "fp8" and qconfig["fmt"] == "e4m3" and qconfig["weight_block_size"] == [128, 128], "quantization")
    index = read(meta / "model.safetensors.index.json")["weight_map"]
    require(not any("expert" in n or ".mlp.gate." in n for n in index), "dense model must have no experts/router")
    expected = expected_shapes(config)
    require(set(expected) == set(index), "config-derived tensor names != index")
    shards, directory = [], {}
    package = read(ROOT / "repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json")
    require((package["repository"], package["revision"], package["total_weight_bytes"]) == (REPO, REV, PACKAGE_BYTES), "package identity")
    package_files = {f["path"]: f for f in package["lfs_files"] if f["path"].endswith(".safetensors")}
    require(set(package_files) == set(index.values()), "package shard coverage")
    for shard in sorted(set(index.values())):
        key = "headers/" + shard + ".json"
        source = sources[key]
        prefix = bytes.fromhex(source["prefix_hex"])
        require(len(prefix) == 8, "prefix length")
        length = int.from_bytes(prefix, "little")
        require(length == source["header_bytes"] and source["prefix_range"] == [0, 7] and source["header_range"] == [8, 7+length], "header range")
        info = files[shard]
        require(source["file_bytes"] == info["size"] == package_files[shard]["bytes"], "shard size")
        require(source["publisher_lfs_sha256"] == info["lfs"]["sha256"] == package_files[shard]["sha256"], "publisher shard hash")
        header = parse_header((meta / key).read_bytes(), info["size"], length)
        require(set(header) == {n for n, f in index.items() if f == shard}, "shard/index coverage")
        for name, item in header.items():
            require(name not in directory, "duplicate tensor across shards")
            require((item["shape"], item["dtype"]) == expected[name], "config shape/dtype: " + name)
            component, residency = classify(name)
            size = math.prod(item["shape"]) * WIDTH[item["dtype"]]
            strides, stride = [], 1
            for dim in reversed(item["shape"]):
                strides.insert(0, stride)
                stride *= dim
            module = name.removesuffix(".weight")
            exclusions = [x for x in qconfig["modules_to_not_convert"] if module == x or module.startswith(x + ".")]
            row = {"name": name, "shard": shard, "dtype": item["dtype"], "shape": item["shape"],
                   "strides_elements": strides, "data_offsets": item["data_offsets"],
                   "file_offsets": [8+length+x for x in item["data_offsets"]], "bytes": size,
                   "component": component, "residency_class": residency, "exclusion_matches": exclusions}
            if item["dtype"] == "F8_E4M3":
                scale = name + "_scale_inv"
                require(scale in header and header[scale]["shape"] == [(x+127)//128 for x in item["shape"]], "missing/wrong block scales")
                require(not exclusions, "FP8 tensor excluded by publisher")
                row["format"] = {"kind": "block_fp8_e4m3", "block_shape": [128, 128], "scale_tensor": scale,
                                 "stored_scale_name": "weight_scale_inv", "scale_dtype": header[scale]["dtype"]}
            elif name.endswith(".weight_scale_inv"):
                weight = name.removesuffix("_scale_inv")
                require(header[weight]["dtype"] == "F8_E4M3", "orphan scale")
                row["format"] = {"kind": "block_scale", "weight_tensor": weight}
            else:
                row["format"] = {"kind": "unquantized", "preserve_storage_dtype": True}
                row["format"]["exclusion_basis"] = "publisher module exclusion" if exclusions else "embedding/final norm is not a quantized linear projection; exact BF16 header is authoritative"
                require(bool(exclusions) or component in {"embedding", "final_norm"}, "unexplained unquantized tensor: " + name)
            directory[name] = row
        shards.append({"file": shard, "file_bytes": info["size"], "header_and_prefix_bytes": length+8,
                       "payload_bytes": info["size"]-length-8, "publisher_lfs_sha256": info["lfs"]["sha256"],
                       "payload_hash_verified": False})
    totals = {key: defaultdict(int) for key in ("component", "residency_class", "dtype")}
    for row in directory.values():
        for key in totals:
            totals[key][row[key]] += row["bytes"]
    payload = sum(row["bytes"] for row in directory.values())
    overhead = sum(s["header_and_prefix_bytes"] for s in shards)
    require(payload + overhead == sum(s["file_bytes"] for s in shards) == PACKAGE_BYTES, "package byte reconciliation")
    dtype_elements = Counter()
    scale_elements = Counter()
    for row in directory.values():
        dtype_elements[row["dtype"]] += math.prod(row["shape"])
        if row["format"]["kind"] == "block_scale":
            scale_elements[row["dtype"]] += math.prod(row["shape"])
    require(dict(dtype_elements - scale_elements) == api["safetensors"]["parameters"], "HF aggregate excludes scales")
    require(sum((dtype_elements - scale_elements).values()) == api["safetensors"]["total"], "HF parameter total")
    tensor_contract = {
        "schema": "own-xpu-runtime.packet1.tensor-contract.v1", "repository": REPO, "revision": REV,
        "provenance": "Exact names/dtypes/shapes/offsets from pinned HF index and header-only metadata; shape formulas independently checked against config by contract-checks.py.",
        "ownership": {"directory": "tensor directory owns file mappings, shapes, strides, quant metadata and identities",
                      "component": "model-specific graph component owns operations/arithmetic; native_mtp includes its merge/norms and block",
                      "allocation": "placement plan owns immutable-weight arena and all residency decisions; no allocation admitted here",
                      "executor": "queues/events/graphs only; no weight ownership inferred from Python views"},
        "scope": "metadata-only; no payload authentication, dequantization, loader implementation, memory admission or native qualification",
        "scale_semantics": "Preserve publisher weight_scale_inv tensors and BF16 storage. Numerical dequantization/cast convention must be proven with known-value fixtures in packet 2; not inferred from the suffix here.",
        "storage_vs_compute": "BF16 exclusions stay BF16 on disk. Certified runtime profile uses W8A16, FP16 activation/KV and FP32 GDN state; no storage dtype is silently rewritten.",
        "unsupported_formats": ["GGUF", "INT4/AutoRound/compressed-tensors", "other FP8 encodings or block sizes", "unknown tensor names/dtypes", "zero-size tensors", "pickle or model-supplied Python"],
        "residency_note": "Classes are byte accounting for a future single-card placement, not measured allocations. Embedding device/UVA choice is unresolved; vision is excluded. Host mappings, KV/state, graph pools, scratch, shadows, staging and allocator overhead are not checkpoint tensors.",
        "tensor_count": len(directory), "layers": [{"layer": i, "kind": kind, "tensor_count": sum(n.startswith(f"model.language_model.layers.{i}.") for n in directory)} for i, kind in enumerate(c["layer_types"])],
        "totals_bytes": {**{key: dict(sorted(value.items())) for key, value in totals.items()},
                         "tensor_payload": payload, "headers_and_prefixes": overhead, "package_files": PACKAGE_BYTES, "unexplained_difference": 0},
        "hf_parameter_reconciliation": {"all_stored_elements": dict(dtype_elements), "block_scale_elements_excluded_from_hf_parameter_count": dict(scale_elements), "hf_parameter_elements": api["safetensors"]},
        "shards": shards, "tensors": [directory[n] for n in sorted(directory)]}
    suite, oracle = read(ROOT / SUITE), read(ROOT / ORACLE)
    require(len(suite["prompts"]) == len(oracle["rows"]) == 12, "oracle/suite row count")
    rows = []
    for prompt, row in zip(suite["prompts"], oracle["rows"], strict=True):
        require(prompt["id"] == row["prompt_id"], "oracle prompt order")
        require(sha(prompt["prompt"].encode()) == row["prompt_sha256"], "prompt text hash")
        ids = row["token_ids"]
        require(ids and all(type(t) is int and 0 <= t < c["vocab_size"] for t in ids), "oracle token range")
        require(len(ids) == row["completion_tokens"] == row["stream_token_id_count"] <= 512, "oracle length")
        require(row["cached_tokens"] == 0, "oracle cached prompt")
        rows.append({"prompt_id": row["prompt_id"], "prompt_class": row["prompt_class"],
                     "prompt_sha256": row["prompt_sha256"], "length": len(ids),
                     "sha256": sha(canonical(ids)), "token_ids": ids})
    require(len({r["prompt_id"] for r in rows}) == 12 and len({r["prompt_class"] for r in rows}) == 6, "oracle uniqueness/classes")
    arrays = {"schema": "own-xpu-runtime.packet1.oracle-token-ids.v1", "source": file_pin(ORACLE),
              "provenance": "Verbatim token_ids extracted from tracked rows in original suite order; no model or tokenizer execution.",
              "hash_encoding": "UTF-8 compact JSON (comma/colon separators, no newline); per-row hashes cover token_ids only; arrays_sha256 covers ordered list of all 12 token arrays",
              "arrays_sha256": sha(canonical([r["token_ids"] for r in rows])), "row_count": 12,
              "total_tokens": sum(r["length"] for r in rows), "rows": rows}
    tokenizer_files = []
    for name in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "chat_template.jinja", "generation_config.json"):
        f = files[name]
        tokenizer_files.append({"path": name, "bytes": f["size"], "git_blob_sha1": f["blobId"],
                                "publisher_lfs_sha256": f.get("lfs", {}).get("sha256"),
                                "metadata_fetched": name in sources,
                                "local_sha256": sources[name]["sha256"] if name in sources else None})
    identity = {
        "schema": "own-xpu-runtime.packet1.identity.v1", "repository": REPO, "revision": REV,
        "provenance": "Official pinned HF metadata plus unchanged tracked config/receipt and fixed suite/oracle; generated by contract-checks.py.",
        "architecture": config["architectures"], "text_only_stage1": True, "dense_not_moe": True,
        "text_config": c, "quantization_config": qconfig,
        "tracked_config": file_pin(LANE + "/data/qwen27-official-config.json"),
        "tracked_config_receipt": file_pin(LANE + "/data/qwen27-config-receipt.json"),
        "metadata_sources": {key: {"sha256": value["sha256"], "bytes": value["bytes"], "url": value["url"]} for key, value in sorted(sources.items())},
        "tokenizer": {"requirements": read(meta / "tokenizer_config.json"), "required_files": tokenizer_files,
                      "generation_config": read(meta / "generation_config.json"),
                      "oracle_input_policy": "Raw completions prompts exactly as suite UTF-8 strings; no system prompt or chat template, no added BOS/prefix. Preserve special-token mapping and regex. Tokenizer execution/parity remains untested.",
                      "chat_policy": "Pinned template is a future chat requirement, not applied to this completions oracle.",
                      "sampling_policy": "Oracle temperature=0, top_p=1, seed=42 overrides publisher sampling defaults. Preserve recorded EOS behavior and 512 cap; do not manufacture EOS tokens.",
                      "unfetched_note": "Tokenizer vocabulary/merges payloads are only pinned by publisher blob/LFS metadata; their bytes were not fetched or SHA256-verified locally."},
        "suite": file_pin(SUITE), "oracle": file_pin(ORACLE),
        "oracle_request_identity": oracle["run_identity"],
        "oracle_arrays": {"path": "oracle-token-ids.json", "sha256": sha(encoded(arrays)), "row_count": 12,
                          "arrays_sha256": arrays["arrays_sha256"], "total_tokens": arrays["total_tokens"]},
        "runtime_requirements": {"arithmetic": "certified W8A16", "activation_dtype": "FP16", "kv_dtype": "FP16", "gdn_state_dtype": "FP32", "target_unchanged": True, "prompt_cache_reuse": False},
        "tensor_contract": {"path": "tensor-contract.json", "sha256": sha(encoded(tensor_contract))},
        "remaining_gates": "No payload hashes, CPU dequant known-values, native runtime, speed or output parity established in packet 1."}
    return {"identity.json": identity, "tensor-contract.json": tensor_contract, "oracle-token-ids.json": arrays}


def fixture_checks():
    fixtures = read(HERE / "parser-fixtures.json")
    results = []
    for case in fixtures["cases"]:
        body = case["header_json"].encode()
        try:
            parse_header(body, case["file_bytes"], case["declared_length"])
            accepted, reason = True, None
        except (ValueError, UnicodeError, TypeError, KeyError) as error:
            accepted, reason = False, str(error)
        require(accepted == case["accept"], "fixture verdict: " + case["name"])
        if not accepted:
            require(case["error_contains"] in reason, "unexpected rejection: " + case["name"] + ": " + reason)
        results.append({"name": case["name"], "accepted": accepted, "passed": True, "reason": reason})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-contracts", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    require(os.environ.get("OMP_NUM_THREADS") == "2", "run with OMP_NUM_THREADS=2")
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, "run at nice 19")
    fixtures = fixture_checks()
    products = derive()
    # Build twice to prove stable output ordering/encoding, with no clock in manifests.
    require({k: encoded(v) for k, v in products.items()} == {k: encoded(v) for k, v in derive().items()}, "nondeterministic manifest")
    for name, value in products.items():
        if args.write_contracts:
            (HERE / name).write_bytes(encoded(value))
        require((HERE / name).read_bytes() == encoded(value), "derived contract differs: " + name)
    receipt = {"schema": "own-xpu-runtime.packet1.check-receipt.v1", "verdict": "PASS",
               "exit_gate": "packet1_cpu_identity_and_tensor_contract", "stage1_complete": False,
               "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "host": socket.gethostname(), "python": sys.version, "nice": os.getpriority(os.PRIO_PROCESS, 0),
               "OMP_NUM_THREADS": os.environ["OMP_NUM_THREADS"],
               "command": "nice -n 19 env OMP_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage1/packet1/contract-checks.py --receipt experiments/own-xpu-runtime/stage1/packet1/check-receipt.json",
               "files": {n: sha((HERE / n).read_bytes()) for n in [*products, "contract-checks.py", "parser-fixtures.json", "fetch-metadata.py", "metadata/fetch-receipt.json"]},
               "oracle_rows": 12, "oracle_lengths": [r["length"] for r in products["oracle-token-ids.json"]["rows"]],
               "tensor_count": products["tensor-contract.json"]["tensor_count"],
               "totals_bytes": products["tensor-contract.json"]["totals_bytes"], "parser_fixtures": fixtures,
               "checks": ["source/config/suite/oracle hashes", "official revision/index/shard coverage", "64 dense layers: 48 GDN / 16 full attention, one MTP block", "independent config-derived shape table", "checked byte products/offsets/no overlaps/no gaps", "FP8 scale pairing/exclusions and dtype census", "package publisher hashes/sizes (metadata only)", "12 oracle arrays/ranges/lengths/prompt hashes", "deterministic manifests regenerated twice", "malformed-header rejection"],
               "mismatches": ["Plan kernel-budget example assumes F32 scales; actual pinned headers store every weight_scale_inv in BF16. One 17408x5120 matrix plus scales is 89139840 bytes, not 89150720. No plan or checkpoint bytes changed.", "Tensor payload is 203664 bytes smaller than package file total: exactly 66 header JSON regions plus 8-byte length prefixes.", "HF aggregate parameter count excludes 1507520 BF16 block-scale elements (3015040 stored bytes); full tensor contract includes them."],
               "limitations": "Metadata only; no payload authentication, tokenizer execution, dequantization or native/performance gate."}
    if args.receipt:
        args.receipt.write_bytes(encoded(receipt))
    print(json.dumps({"verdict": receipt["verdict"], "tensor_count": receipt["tensor_count"], "parser_cases": len(fixtures), "totals_bytes": receipt["totals_bytes"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)

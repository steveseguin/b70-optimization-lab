#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("check-tp2-sealed-gates.py")
SPEC = importlib.util.spec_from_file_location("check_tp2_sealed_gates", SCRIPT)
assert SPEC and SPEC.loader
gates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gates)


KEY_A = "a" * 64
KEY_B = "b" * 64
SUITE_PAYLOAD = {
    "suite_id": "qwen36-27b-int4-independent-validation-20260815-v1",
    "version": 1,
    "prompts": [
        {"id": f"p{index}", "prompt": f"fixture prompt {index}"}
        for index in range(25)
    ],
}
SUITE_BYTES = (json.dumps(SUITE_PAYLOAD, sort_keys=True) + "\n").encode()
SUITE_SHA = hashlib.sha256(SUITE_BYTES).hexdigest()
TRACE_REQ_ID = f"{gates.REPLAY_MICROSCOPE_REQ_BASE}-deadbeef"


def identity_text(
    fixture: "ArmGateTests",
    *,
    pad: int = 1,
    tp: int = 2,
    replay_bypass: int = 0,
    request_replay_bypass: int = 0,
    vllm_diff_sha256: str = hashlib.sha256(b"").hexdigest(),
) -> str:
    cache_root = fixture.cache_root
    graph_manifest = fixture.graph_manifest
    cache_dir = cache_root / "torch_compile_cache" / "b99160ae76"
    stage = fixture.stage
    package = stage / "vllm_xpu_kernels"
    input_manifest_sha = hashlib.sha256(manifest_bytes(cache_root)).hexdigest()
    graph_manifest_sha = hashlib.sha256(graph_manifest.read_bytes()).hexdigest()
    return "\n".join(
        (
            f"tensor_parallel_size={tp}",
            "validation_mode=spec-native-partition-exact-native",
            "gpu_index=2,3",
            f"model_dir={fixture.model_dir}",
            f"model_manifest={fixture.model_manifest}",
            f"model_manifest_sha256={gates.sha256_file(fixture.model_manifest)}",
            "model_verification_policy=direct-and-ordinary-fail-closed",
            "model_verify_status=verified",
            f"model_verify_json={fixture.model_verify}",
            f"model_verify_json_sha256={gates.sha256_file(fixture.model_verify)}",
            f"verify_model_script={fixture.verifier}",
            f"verify_model_script_sha256={gates.sha256_file(fixture.verifier)}",
            f"vllm_cache_root={cache_root}",
            "compilation_config="
            + json.dumps(
                {
                    "cache_dir": str(cache_dir),
                    "use_inductor_graph_partition": True,
                    "pass_config": {"fuse_rope_kvcache_cat_mla": False},
                    "cudagraph_mode": "PIECEWISE",
                    "cudagraph_capture_sizes": [6],
                    "max_cudagraph_capture_size": 6,
                },
                separators=(",", ":"),
            ),
            f"onednn_int4_determinism_pad={pad}",
            "enable_mtp=1",
            "num_speculative_tokens=5",
            "enable_xpu_graph=1",
            "xpu_graph=1",
            "vllm_xpu_enable_xpu_graph=1",
            "vllm_xpu_force_graph_with_comm=1",
            "vllm_xpu_graph_noop_comm_capture=1",
            "disable_spec_decode_cudagraph_replay="
            + ("1" if replay_bypass else ""),
            f"expected_disable_spec_decode_cudagraph_replay={replay_bypass}",
            "decode_cudagraph_replay_eager_every_n_requests="
            + ("1" if request_replay_bypass else ""),
            "expected_decode_cudagraph_replay_eager_every_n_requests="
            + str(request_replay_bypass),
            "draft_disable_cudagraphs=0",
            f"expected_vllm_diff_sha256={vllm_diff_sha256}",
            "max_model_len=2048",
            "max_num_batched_tokens=1024",
            "max_num_seqs=1",
            "gpu_memory_utilization=0.95",
            "pythonhashseed=0",
            "draft_lm_head_int4=1",
            "draft_lm_head_int4_group_size=128",
            "draft_lm_head_int4_scale_dtype=bf16",
            "draft_lm_head_int4_fallback_margin=0",
            "gdn_native_spec_decode=1",
            "gdn_native_spec_recurrent_serial_exact=",
            "gdn_native_fallback=0",
            "gdn_replayssm_spec=0",
            "gdn_spec_persistent_scratch=1",
            "gdn_capture_native_spec=1",
            "ddtree_capture_gdn_core=0",
            "ddtree_full_graph=0",
            "onednn_int4_completion_barrier=1",
            "onednn_int4_input_dependency=1",
            "onednn_int4_input_dependency_scope=all_target",
            "onednn_int8_completion_barrier=1",
            "onednn_int8_input_dependency=1",
            "fa2_force_chunk_decode=1",
            "lm_head_int8=1",
            "lm_head_int8_scope=all",
            "lm_head_int8_scale_dtype=bf16",
            "deterministic_greedy_margin=0",
            "sync_after_model_forward=0",
            "run_smoke=1",
            "run_bench=1",
            "run_quality=0",
            "bench_max_tokens=512",
            "bench_metric_tokens=100",
            "vllm_extra_args=--dtype float16",
            "xpu_compile_allgather_custom_op=1",
            "ccl_atl_transport=ofi",
            "ccl_topo_p2p_access=1",
            "ccl_ze_ipc_exchange=pidfd",
            "oneccl_candidate_path=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0",
            "oneccl_candidate_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700",
            "oneccl_kernels_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9",
            "oneccl_source_top_commit=b52f40c07f0b140e6aba87548c80720a350a9827",
            "oneccl_libccl_commit=4ceafd15c03ce46f11eeaf91781a92afebd3cecf",
            "tp2_sealed_gates_required=1",
            "compile_cache_unchanged_required=1",
            "no_compile_cache_writes_required=1",
            f"run_arm_script_sha256={gates.sha256_file(fixture.run_arm_snapshot)}",
            f"sealed_gate_checker_sha256={gates.sha256_file(fixture.checker_snapshot)}",
            f"campaign_driver={fixture.driver_source}",
            f"campaign_driver_sha256={gates.sha256_file(fixture.driver_snapshot)}",
            f"validation_input_env_sha256={gates.sha256_file(fixture.input_env)}",
            f"common_runner_sha256={gates.sha256_file(fixture.common_snapshot)}",
            f"candidate_entrypoint={fixture.candidate_source}",
            f"candidate_entrypoint_sha256={gates.sha256_file(fixture.candidate_snapshot)}",
            f"serve_vllm_sha256={gates.sha256_file(fixture.serve_snapshot)}",
            "require_xpu_modules_under_stage=1",
            f"xpu_kernels_src={stage}",
            f"xpu_python_package_path={package}",
            f"xpu_native_extension_path={package}/_xpu_C.abi3.so",
            f"xpu_core_extension_path={package}/_C.abi3.so",
            f"xpu_moe_extension_path={package}/_moe_C.abi3.so",
            f"xpu_fa_extension_path={package}/_vllm_fa2_C.abi3.so",
            f"xpu_native_extension_sha256={gates.sha256_file(fixture.native)}",
            f"xpu_core_extension_sha256={gates.sha256_file(fixture.core)}",
            f"xpu_moe_extension_sha256={gates.sha256_file(fixture.moe)}",
            f"xpu_fa_extension_sha256={gates.sha256_file(fixture.fa)}",
            f"compile_cache_input_manifest_sha256={input_manifest_sha}",
            f"validation_suite_sha256={SUITE_SHA}",
            f"graph_stage_manifest={graph_manifest}",
            f"graph_stage_manifest_sha256={graph_manifest_sha}",
            f"quality_baseline_json={fixture.baseline}",
            f"quality_baseline_json_sha256={gates.sha256_file(fixture.baseline)}",
            "expected_onednn_int4_determinism_pad_markers=2",
            "expected_sync_after_model_forward=0",
            "expected_parity_peer_checksum_manifest_sha256=",
            "expected_compile_cache_direct_loads=2",
            "expected_aot_direct_loads=4",
            "expected_compile_cache_namespace=b99160ae76",
            "expected_compile_cache_outer_roles=backbone,eagle_head",
            f"expected_aot_cache_keys={KEY_A},{KEY_B}",
            f"expected_suite_sha256={SUITE_SHA}",
            f"expected_quality_baseline_sha256={gates.sha256_file(fixture.baseline)}",
            "expected_report_only_b2_bench_sha256=",
            "parity_peer_bench=",
            "parity_peer_bench_sha256=",
            "parity_peer_bench_snapshot=",
            "parity_peer_bench_snapshot_sha256=",
            "target_token_bench=",
            "target_token_bench_sha256=",
            "target_token_bench_snapshot=",
            "target_token_bench_snapshot_sha256=",
            "report_only_b2_bench=",
            "report_only_b2_bench_sha256=",
            "report_only_b2_bench_snapshot=",
            "report_only_b2_bench_snapshot_sha256=",
            "",
        )
    )


def good_log(cache_root: Path) -> str:
    cache_dir = cache_root / "torch_compile_cache" / "b99160ae76"
    aot_root = cache_root / "torch_compile_cache" / "torch_aot_compile"
    lines = [
        "(EngineCore pid=9) INFO config: tensor_parallel_size=2 "
        "num_spec_tokens=5 dtype=torch.float16 quantization=inc seed=0 "
        "enable_prefix_caching=False cudagraph_metrics=False",
        "(EngineCore pid=9) INFO Asynchronous scheduling is enabled.",
        "(Worker_TP0 pid=20) INFO Prepared experimental XPU INT8 lm_head: "
        "prefix=language_model.lm_head scope=all",
        "(Worker_TP1 pid=21) INFO Prepared experimental XPU INT8 lm_head: "
        "prefix=language_model.lm_head scope=all",
        "(Worker_TP0 pid=20) INFO Prepared experimental XPU INT4 draft lm_head: "
        "group_size=128",
        "(Worker_TP1 pid=21) INFO Prepared experimental XPU INT4 draft lm_head: "
        "group_size=128",
    ]
    for role in ("backbone", "eagle_head"):
        lines.extend(
            (
                f"(Worker_TP0 pid=10) INFO Using cache directory: "
                f"{cache_dir}/rank_0_0/{role} for vLLM's torch.compile",
                "(Worker_TP0 pid=10) INFO Directly load the compiled graph(s) "
                "for compile range (1, 1024) from the cache, took 0.123 s",
            )
        )
    for key in (KEY_A, KEY_B):
        for rank in (0, 1):
            lines.append(
                f"(Worker_TP{rank} pid={20 + rank}) INFO Directly load AOT "
                f"compilation from path {aot_root}/{key}/rank_{rank}_0/model"
            )
    lines.extend(
        (
            f"[rank0]: Warning: {gates.PAD_MARKER}",
            f"[rank1]: Warning: {gates.PAD_MARKER}",
        )
    )
    return "\n".join(lines) + "\n"


def replay_bypass_log() -> str:
    lines = []
    for rank in (0,):
        lines.extend(
            (
                f"(Worker_TP{rank} pid={20 + rank}) INFO Skipping 1 uniform "
                "PIECEWISE speculative decode CUDA graph captures because "
                "VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1.",
                f"(Worker_TP{rank} pid={20 + rank}) INFO Disabling speculative "
                "drafter CUDA graph keys on XPU because "
                "VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1.",
            )
        )
    lines.extend(
        (
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 0% 0/1",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100% 1/1",
            "(Worker_TP0 pid=20) INFO Graph capturing finished in 1 secs, "
            "took 0.42 GiB",
            "(APIServer pid=19) INFO SpecDecoding metrics: Mean acceptance "
            "length: 3.03, Accepted throughput: 2.98 tokens/s, Drafted "
            "throughput: 7.34 tokens/s, Accepted: 71 tokens, Drafted: 175 "
            "tokens, Per-position acceptance rate: 0.743, 0.571, 0.371, "
            "0.229, 0.114, Avg Draft acceptance rate: 40.6%",
        )
    )
    return "\n".join(lines) + "\n"


def target_request_replay_bypass_log() -> str:
    lines = [
        "(Worker_TP0 pid=20) INFO XPU target/verifier request-selected uniform "
        "PIECEWISE replay bypass engaged: every_n_requests=1 "
        "uniform_decode_query_len=6.",
        "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 0% 0/1",
        "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100% 1/1",
        "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE): 100% 1/1",
        "Capturing CUDA graphs (decode, PIECEWISE): 0% 0/1",
        "Capturing CUDA graphs (decode, PIECEWISE): 100% 1/1",
        "Capturing CUDA graphs (decode, PIECEWISE): 100% 1/1",
        "(Worker_TP0 pid=20) INFO Graph capturing finished in 1 secs, "
        "took 0.86 GiB",
        "(APIServer pid=19) INFO SpecDecoding metrics: Mean acceptance "
        "length: 3.03, Accepted throughput: 2.98 tokens/s, Drafted "
        "throughput: 7.34 tokens/s, Accepted: 71 tokens, Drafted: 175 "
        "tokens, Per-position acceptance rate: 0.743, 0.571, 0.371, "
        "0.229, 0.114, Avg Draft acceptance rate: 40.6%",
    ]
    return "\n".join(lines) + "\n"


def manifest_bytes(cache_root: Path, *, tree: str = "c" * 64) -> bytes:
    return (
        json.dumps(
            {
                "format": "b70-canonical-tree-manifest-v1",
                "root_at_capture": str(cache_root / "torch_compile_cache"),
                "tree_sha256": tree,
                "entry_count": 7,
                "file_count": 4,
                "total_file_bytes": 1234,
                "entries": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def replay_records(*, sampled_token: int = 71093) -> list[dict]:
    common = {
        "tp_rank": 0,
        "req_ids": [TRACE_REQ_ID],
        "matched_req_ids": [TRACE_REQ_ID],
        "requests": [
            {
                "req_id": TRACE_REQ_ID,
                "num_prompt_tokens_cpu": 849,
                "num_tokens_no_spec": 849,
            }
        ],
    }

    def tensor() -> dict:
        return {"shape": [1], "numel": 1, "nan": 0, "posinf": 0, "neginf": 0}

    rows = []
    for stage in gates.REPLAY_MICROSCOPE_STAGES:
        row = dict(common)
        row["stage"] = stage
        tensor_name = {
            "inputs": "input_ids",
            "hidden_after_forward": "hidden_states",
            "sample_hidden": "sample_hidden_states",
            "logits_after_compute": "logits",
            "pre_sample": "logits",
            "sampler_output": "sampled_token_ids",
        }[stage]
        row["tensors"] = {tensor_name: tensor()}
        if stage in ("logits_after_compute", "pre_sample"):
            row["logit_rows"] = [
                {
                    "row": 0,
                    "role": "sample",
                    "req_index": 0,
                    "req_id": TRACE_REQ_ID,
                    "num_tokens_no_spec_cpu": 849,
                    "logits_topk": {
                        "token_ids": [71093, 13102],
                        "values": [1.0, 0.5],
                        "top1_top2_margin": 0.5,
                    }
                }
            ]
        if stage == "sampler_output":
            row["tensors"][tensor_name]["head"] = [sampled_token]
        rows.append(row)
    return rows


def bench(path: Path, token_rows: list[list[int]], *, order: list[int] | None = None) -> None:
    order = order or list(range(len(token_rows)))
    rows = []
    for position, source in enumerate(order):
        rows.append(
            {
                "prompt_index": position,
                "prompt_id": f"p{source}",
                "prompt_sha256": f"{source + 1:064x}",
                "token_ids": token_rows[source],
                "sha256": "same-output-sha-for-test",
            }
        )
    path.write_text(
        json.dumps(
            {
                "run_identity": {
                    "api_mode": "chat",
                    "max_tokens": 512,
                    "return_token_ids": True,
                    "seed": 1,
                },
                "fresh_response_validity": {
                    "valid": True,
                    "suite_id": "fixture-suite",
                    "prompt_count": len(rows),
                    "cached_tokens": [0] * len(rows),
                    "cached_tokens_all_zero": True,
                    "each_prompt_run_once": True,
                    "prompts_are_unique": True,
                    "response_reuse": False,
                    "history_acceleration": False,
                    "ngram_history_acceleration": False,
                    "context_checkpoints_or_prefix_reuse": False,
                    "return_token_ids_requested": True,
                    "primary_metric_tokens": 100,
                },
                "realistic_final_gate": {"passed": True},
                "rows": rows,
            }
        )
    )


class ArmGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "arm"
        self.cache_root = Path(self.temp.name) / "cache"
        (self.root / "run").mkdir(parents=True)
        self.stage = Path(self.temp.name) / "stage"
        package = self.stage / "vllm_xpu_kernels"
        package.mkdir(parents=True)
        self.native = package / "_xpu_C.abi3.so"
        self.core = package / "_C.abi3.so"
        self.moe = package / "_moe_C.abi3.so"
        self.fa = package / "_vllm_fa2_C.abi3.so"
        for path in (self.native, self.core, self.moe, self.fa):
            path.write_bytes((path.name + " fixture").encode())
        self.model_dir = Path(self.temp.name) / "model"
        self.model_dir.mkdir()
        self.model_manifest = Path(self.temp.name) / "model.json"
        self.model_manifest.write_text('{"fixture":"model"}\n')
        self.verifier = Path(self.temp.name) / "verify.py"
        self.verifier.write_text("# fixture verifier\n")
        self.baseline = Path(self.temp.name) / "quality-baseline.json"
        self.baseline.write_text('{"fixture":true}\n')
        self.graph_manifest = Path(self.temp.name) / "graph.sha256"
        self.graph_manifest.write_text("fixture graph manifest\n")
        self.run_arm_snapshot = self.root / "run" / "run-arm.sh.snapshot"
        self.checker_snapshot = (
            self.root / "run" / "check-tp2-sealed-gates.py.snapshot"
        )
        self.driver_snapshot = self.root / "run" / "campaign-driver.sh.snapshot"
        self.input_env = self.root / "run" / "validation-input.env"
        self.common_snapshot = self.root / "run" / "run-vllm-candidate.sh.snapshot"
        self.candidate_source = (
            Path(self.temp.name) / "run-tp2-fullgraph-transaction-candidate.sh"
        )
        self.candidate_snapshot = (
            self.root / "run" / "run-tp2-fullgraph-transaction-candidate.sh.snapshot"
        )
        self.driver_source = Path(self.temp.name) / "driver.sh"
        self.serve_snapshot = self.root / "run" / "serve-vllm.sh.snapshot"
        for path in (
            self.run_arm_snapshot,
            self.checker_snapshot,
            self.driver_snapshot,
            self.input_env,
            self.common_snapshot,
            self.candidate_snapshot,
            self.serve_snapshot,
        ):
            path.write_text(f"fixture {path.name}\n")
        (self.root / "run" / "llm-optimizations.git-head").write_text("f" * 40 + "\n")
        (self.root / "run" / "llm-optimizations.working.patch").write_bytes(b"")
        (self.root / "run" / "vllm.git-head").write_text(
            "44fc8fde09fc311d3099dab10366b672d9142ea4\n"
        )
        (self.root / "run" / "vllm-xpu-kernels.git-head").write_text(
            "2dd55f380df753a10a88fcd9e96192561066e713\n"
        )
        (self.root / "run" / "vllm.working.patch").write_bytes(b"")
        (self.root / "run" / "vllm-xpu-kernels.working.patch").write_bytes(b"")
        self.model_verify = self.root / "run" / "model-verify.json"
        self.model_verify.write_text(
            json.dumps(
                {
                    "status": "verified",
                    "read_modes": ["odirect"],
                    "files": [
                        {
                            "path": f"file-{index}",
                            "ok": True,
                            "direct_ok": True,
                            "ordinary_ok": True,
                            "paths_coherent": True,
                        }
                        for index in range(19)
                    ],
                }
            )
        )
        (self.root / "run" / "identity.env").write_text(
            identity_text(self)
        )
        (self.root / "run" / "server.stdout.log").write_text(good_log(self.cache_root))
        (self.root / "run" / "supervision.log").write_text(
            "fixture stop_group begin\n"
            "fixture stop_group complete: group empty\n"
        )
        payload = manifest_bytes(self.cache_root)
        (self.root / "compile-cache-input-manifest.json").write_bytes(payload)
        (self.root / "compile-cache-output-manifest.json").write_bytes(payload)
        (self.root / "validation-suite.json").write_bytes(SUITE_BYTES)
        rows = []
        for index, prompt in enumerate(SUITE_PAYLOAD["prompts"]):
            rows.append(
                {
                    "prompt_index": index,
                    "prompt_id": prompt["id"],
                    "prompt_sha256": hashlib.sha256(
                        prompt["prompt"].encode()
                    ).hexdigest(),
                    "token_ids": [index + 1],
                }
            )
        (self.root / "data").mkdir()
        (self.root / "data" / "bench.json").write_text(
            json.dumps(
                {
                    "run_identity": {
                        "api_mode": "chat",
                        "max_tokens": 512,
                        "return_token_ids": True,
                        "seed": 1,
                    },
                    "fresh_response_validity": {
                        "valid": True,
                        "suite_id": SUITE_PAYLOAD["suite_id"],
                        "prompt_count": 25,
                        "cached_tokens": [0] * 25,
                        "cached_tokens_all_zero": True,
                        "each_prompt_run_once": True,
                        "prompts_are_unique": True,
                        "response_reuse": False,
                        "history_acceleration": False,
                        "ngram_history_acceleration": False,
                        "context_checkpoints_or_prefix_reuse": False,
                        "return_token_ids_requested": True,
                        "primary_metric_tokens": 100,
                    },
                    "realistic_final_gate": {"passed": True},
                    "rows": rows,
                }
            )
        )
        self.args = argparse.Namespace(
            arm_root=str(self.root),
            expected_namespace="b99160ae76",
            expected_outer_role=["backbone", "eagle_head"],
            expected_outer_loads=2,
            expected_aot_key=[KEY_A, KEY_B],
            expected_aot_loads=4,
            expected_pad_markers=2,
            expected_sync_after_model_forward=0,
            expected_disable_spec_decode_cudagraph_replay=0,
            expected_decode_cudagraph_replay_eager_every_n_requests=0,
            expected_vllm_diff_sha256=hashlib.sha256(b"").hexdigest(),
            expected_parity_peer_checksum_manifest_sha256="",
            expected_report_only_b2_bench_sha256="",
            expected_suite_sha256=SUITE_SHA,
            expected_model_dir=str(self.model_dir),
            expected_model_manifest_sha256=gates.sha256_file(self.model_manifest),
            expected_verify_script_sha256=gates.sha256_file(self.verifier),
            expected_cache_root=str(self.cache_root),
            expected_cache_manifest_sha256=hashlib.sha256(payload).hexdigest(),
            expected_graph_manifest_sha256=gates.sha256_file(self.graph_manifest),
            expected_native_sha256=gates.sha256_file(self.native),
            expected_core_sha256=gates.sha256_file(self.core),
            expected_moe_sha256=gates.sha256_file(self.moe),
            expected_fa_sha256=gates.sha256_file(self.fa),
            expected_repo_head="f" * 40,
            require_quality_pass=False,
            require_replay_microscope=False,
            expected_quality_baseline_sha256=gates.sha256_file(self.baseline),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_gate(self):
        return gates.check_arm(self.args)

    def test_happy_tp2(self) -> None:
        result, passed = self.run_gate()
        self.assertTrue(passed, result)
        self.assertEqual(result["pad"]["actual_ranks"], [0, 1])
        self.assertEqual(result["cache_loads"]["actual_aot_loads"], 4)
        self.assertIsNone(result["graph_replay_bypass"])
        self.assertIsNone(result["target_verifier_request_replay_bypass"])

    def test_unexpected_target_request_replay_marker_fails(self) -> None:
        marker = target_request_replay_bypass_log().splitlines()[0]
        log_path = self.root / "run" / "server.stdout.log"
        log_path.write_text(good_log(self.cache_root) + marker + "\n")
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("independent expectation was 0" in error for error in result["errors"])
        )

    def enable_replay_bypass(self) -> None:
        (self.root / "run" / "identity.env").write_text(
            identity_text(self, replay_bypass=1)
        )
        log_path = self.root / "run" / "server.stdout.log"
        log_path.write_text(good_log(self.cache_root) + replay_bypass_log())
        self.args.expected_disable_spec_decode_cudagraph_replay = 1

    def test_replay_bypass_exact_engagement_and_metrics_pass(self) -> None:
        self.enable_replay_bypass()
        result, passed = self.run_gate()
        self.assertTrue(passed, result)
        evidence = result["graph_replay_bypass"]
        self.assertEqual(evidence["target_skip_ranks"], [0])
        self.assertEqual(evidence["drafter_graph_disable_ranks"], [0])
        self.assertEqual(len(evidence["spec_metrics"]), 1)
        self.assertEqual(evidence["capture_inventory"][0]["max_done"], 1)

    def test_replay_bypass_missing_marker_or_decode_capture_fails(self) -> None:
        self.enable_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        text = log_path.read_text()
        log_path.write_text(
            text.replace(
                "(Worker_TP0 pid=20) INFO Disabling speculative drafter CUDA "
                "graph keys on XPU because "
                "VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1.\n",
                "",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("drafter graph-disable" in error for error in result["errors"])
        )

        log_path.write_text(
            text + "Capturing CUDA graphs (decode, PIECEWISE): 100% 1/1\n"
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("capture inventory" in error for error in result["errors"]))

        log_path.write_text(
            text.replace(
                "(Worker_TP0 pid=20) INFO Graph capturing finished in 1 secs, "
                "took 0.42 GiB\n",
                "",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("capture completion" in error for error in result["errors"])
        )

        log_path.write_text(
            text.replace(
                "(Worker_TP0 pid=20) INFO Skipping 1 uniform",
                "(EngineCore pid=9) [rank0] INFO Skipping 1 uniform",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("target replay-bypass marker" in error for error in result["errors"])
        )

    def test_replay_bypass_traceback_lazy_capture_and_metrics_fail(self) -> None:
        self.enable_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        base = log_path.read_text()
        for marker in gates.SPEC_REPLAY_NEGATIVE_MARKERS:
            with self.subTest(marker=marker):
                log_path.write_text(base + marker + "\n")
                result, passed = self.run_gate()
                self.assertFalse(passed)
                self.assertTrue(
                    any("traceback" in error for error in result["errors"])
                )

    def test_replay_bypass_malformed_spec_metrics_fail_closed(self) -> None:
        self.enable_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        log_path.write_text(
            log_path.read_text().replace(
                "Avg Draft acceptance rate: 40.6%",
                "Avg Draft acceptance rate: nan%",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("no exact SpecDecoding" in error for error in result["errors"])
        )

        self.enable_replay_bypass()
        valid_log = log_path.read_text()
        valid_metric = next(
            line for line in valid_log.splitlines() if "SpecDecoding metrics:" in line
        )
        log_path.write_text(
            valid_log
            + valid_metric.replace(
                "Avg Draft acceptance rate: 40.6%",
                "Avg Draft acceptance rate: nan%",
            )
            + "\n"
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("malformed" in error for error in result["errors"]))

        self.enable_replay_bypass()
        log_path.write_text(
            log_path.read_text().replace(
                "Avg Draft acceptance rate: 40.6%",
                "Avg Draft acceptance rate: 40.6% trailing-junk",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("malformed" in error for error in result["errors"])
        )

    def test_replay_bypass_requires_accepted_draft_tokens(self) -> None:
        self.enable_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        log_path.write_text(
            log_path.read_text()
            .replace("Mean acceptance length: 3.03", "Mean acceptance length: 1.00")
            .replace("Accepted throughput: 2.98", "Accepted throughput: 0.00")
            .replace("Accepted: 71 tokens", "Accepted: 0 tokens")
            .replace(
                "Per-position acceptance rate: 0.743, 0.571, 0.371, 0.229, 0.114",
                "Per-position acceptance rate: 0.000, 0.000, 0.000, 0.000, 0.000",
            )
            .replace("Avg Draft acceptance rate: 40.6%", "Avg Draft acceptance rate: 0.0%")
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("no accepted draft tokens" in error for error in result["errors"])
        )

    def enable_target_request_replay_bypass(self) -> None:
        patch = b"fixture target request replay marker patch\n"
        patch_sha = hashlib.sha256(patch).hexdigest()
        (self.root / "run" / "vllm.working.patch").write_bytes(patch)
        (self.root / "run" / "identity.env").write_text(
            identity_text(
                self,
                request_replay_bypass=1,
                vllm_diff_sha256=patch_sha,
            )
        )
        log_path = self.root / "run" / "server.stdout.log"
        log_path.write_text(
            good_log(self.cache_root) + target_request_replay_bypass_log()
        )
        self.args.expected_decode_cudagraph_replay_eager_every_n_requests = 1
        self.args.expected_vllm_diff_sha256 = patch_sha

    def test_target_request_replay_bypass_exact_engagement_passes(self) -> None:
        self.enable_target_request_replay_bypass()
        result, passed = self.run_gate()
        self.assertTrue(passed, result)
        evidence = result["target_verifier_request_replay_bypass"]
        self.assertEqual(evidence["raw_marker_count"], 1)
        self.assertEqual(
            [(item["kind"], item["done_values"]) for item in evidence["capture_inventory"]],
            [("decode", [0, 1]), ("mixed prefill-decode", [0, 1])],
        )
        self.assertEqual(evidence["aggregate_accepted"], 71)
        self.assertEqual(evidence["aggregate_drafted"], 175)

    def test_target_request_replay_bypass_marker_is_strict(self) -> None:
        self.enable_target_request_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        base = log_path.read_text()
        marker = next(
            line
            for line in base.splitlines()
            if gates.TARGET_REQUEST_REPLAY_BYPASS_MARKER in line
        )
        mutations = {
            "wrong actor": marker.replace("Worker_TP0", "EngineCore"),
            "wrong rank": marker.replace("Worker_TP0", "Worker_TP1"),
            "wrong interval": marker.replace("every_n_requests=1", "every_n_requests=2"),
            "wrong query length": marker.replace(
                "uniform_decode_query_len=6", "uniform_decode_query_len=1"
            ),
            "trailing junk": marker + " trailing-junk",
            "duplicate": marker + "\n" + marker,
        }
        for label, replacement in mutations.items():
            with self.subTest(label=label):
                log_path.write_text(base.replace(marker, replacement))
                result, passed = self.run_gate()
                self.assertFalse(passed)
                self.assertTrue(
                    any(
                        "request-selected replay-bypass marker" in error
                        for error in result["errors"]
                    )
                )

    def test_target_request_replay_bypass_preserves_topology_and_drafter(self) -> None:
        self.enable_target_request_replay_bypass()
        log_path = self.root / "run" / "server.stdout.log"
        base = log_path.read_text()
        log_path.write_text(
            base.replace(
                "Capturing CUDA graphs (decode, PIECEWISE): 0% 0/1\n",
                "",
            )
        )
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("three-record" in error for error in result["errors"]))

        log_path.write_text(base + replay_bypass_log())
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("drafter graph-disable marker" in error for error in result["errors"])
        )

        identity = self.root / "run" / "identity.env"
        identity.write_text(
            identity.read_text().replace(
                "draft_disable_cudagraphs=0\n", "draft_disable_cudagraphs=1\n"
            )
        )
        log_path.write_text(base)
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("draft_disable_cudagraphs" in error for error in result["errors"]))

    def test_target_request_replay_bypass_rejects_source_diff_mismatch(self) -> None:
        self.enable_target_request_replay_bypass()
        self.args.expected_vllm_diff_sha256 = "a" * 64
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("expected_vllm_diff_sha256" in error for error in result["errors"]))

        self.args.expected_vllm_diff_sha256 = hashlib.sha256(
            b"fixture target request replay marker patch\n"
        ).hexdigest()
        (self.root / "run" / "vllm.working.patch").write_bytes(b"changed\n")
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("vllm tracked working patch" in error for error in result["errors"]))

    def test_report_only_b2_source_and_snapshot_are_immutable(self) -> None:
        source = Path(self.temp.name) / "b2-bench.json"
        snapshot = self.root / "run" / "report-only-b2-bench.input.json"
        source.write_text('{"fixture":"b2"}\n')
        snapshot.write_bytes(source.read_bytes())
        digest = gates.sha256_file(source)
        identity = self.root / "run" / "identity.env"
        identity.write_text(
            identity.read_text()
            .replace(
                "expected_report_only_b2_bench_sha256=\n",
                f"expected_report_only_b2_bench_sha256={digest}\n",
            )
            .replace(
                "report_only_b2_bench=\n",
                f"report_only_b2_bench={source}\n",
            )
            .replace(
                "report_only_b2_bench_sha256=\n",
                f"report_only_b2_bench_sha256={digest}\n",
            )
            .replace(
                "report_only_b2_bench_snapshot=\n",
                f"report_only_b2_bench_snapshot={snapshot}\n",
            )
            .replace(
                "report_only_b2_bench_snapshot_sha256=\n",
                f"report_only_b2_bench_snapshot_sha256={digest}\n",
            )
        )
        self.args.expected_report_only_b2_bench_sha256 = digest
        result, passed = self.run_gate()
        self.assertTrue(passed, result)

        source.write_text('{"fixture":"changed"}\n')
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("report_only_b2_bench" in error for error in result["errors"]))

    def test_real_arm_cli_happy_path(self) -> None:
        output = Path(self.temp.name) / "gate-output.json"
        argv = [
            str(SCRIPT),
            "arm",
            "--arm-root",
            str(self.root),
            "--expected-namespace",
            self.args.expected_namespace,
            "--expected-outer-role",
            "backbone",
            "--expected-outer-role",
            "eagle_head",
            "--expected-outer-loads",
            "2",
            "--expected-aot-key",
            KEY_A,
            "--expected-aot-key",
            KEY_B,
            "--expected-aot-loads",
            "4",
            "--expected-pad-markers",
            "2",
            "--expected-suite-sha256",
            SUITE_SHA,
            "--expected-model-dir",
            str(self.model_dir),
            "--expected-model-manifest-sha256",
            self.args.expected_model_manifest_sha256,
            "--expected-verify-script-sha256",
            self.args.expected_verify_script_sha256,
            "--expected-cache-root",
            str(self.cache_root),
            "--expected-cache-manifest-sha256",
            self.args.expected_cache_manifest_sha256,
            "--expected-graph-manifest-sha256",
            self.args.expected_graph_manifest_sha256,
            "--expected-native-sha256",
            self.args.expected_native_sha256,
            "--expected-core-sha256",
            self.args.expected_core_sha256,
            "--expected-moe-sha256",
            self.args.expected_moe_sha256,
            "--expected-fa-sha256",
            self.args.expected_fa_sha256,
            "--expected-repo-head",
            self.args.expected_repo_head,
            "--expected-quality-baseline-sha256",
            self.args.expected_quality_baseline_sha256,
            "--output",
            str(output),
        ]
        with mock.patch.object(gates.sys, "argv", argv):
            self.assertEqual(gates.main(), 0)
        self.assertEqual(json.loads(output.read_text())["status"], "passed")

    def test_missing_or_unranked_pad_marker_fails(self) -> None:
        log_path = self.root / "run" / "server.stdout.log"
        text = log_path.read_text().replace(
            f"[rank1]: Warning: {gates.PAD_MARKER}\n", ""
        )
        log_path.write_text(text)
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("pad-marker" in item for item in result["errors"]))

        text += f"Warning: {gates.PAD_MARKER}\n"
        log_path.write_text(text)
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("exactly one rank" in item for item in result["errors"]))

    def test_missing_extra_or_rank_mismatched_aot_fails(self) -> None:
        log_path = self.root / "run" / "server.stdout.log"
        text = log_path.read_text()
        victim = (
            f"(Worker_TP1 pid=21) INFO Directly load AOT compilation from path "
            f"{self.cache_root}/torch_compile_cache/torch_aot_compile/{KEY_B}/rank_1_0/model\n"
        )
        log_path.write_text(text.replace(victim, ""))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("AOT direct-load" in item for item in result["errors"]))

        rank_line = (
            f"(Worker_TP1 pid=21) INFO Directly load AOT compilation from path "
            f"{self.cache_root}/torch_compile_cache/torch_aot_compile/{KEY_A}/rank_1_0/model"
        )
        log_path.write_text(text.replace(rank_line, rank_line.replace("Worker_TP1", "Worker_TP0")))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("actor/path rank" in item for item in result["errors"]))

    def test_wrong_outer_pair_or_compile_marker_fails(self) -> None:
        log_path = self.root / "run" / "server.stdout.log"
        text = log_path.read_text().replace("/eagle_head ", "/wrong_role ")
        log_path.write_text(text)
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("outer" in item.lower() for item in result["errors"]))

        for marker in gates.NEGATIVE_MARKERS:
            with self.subTest(marker=marker):
                log_path.write_text(good_log(self.cache_root) + marker + " fixture\n")
                result, passed = self.run_gate()
                self.assertFalse(passed)
                self.assertTrue(any("compile or save" in item for item in result["errors"]))

    def test_cache_mutation_or_missing_output_fails_closed(self) -> None:
        output = self.root / "compile-cache-output-manifest.json"
        output.write_bytes(manifest_bytes(self.cache_root, tree="d" * 64))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("manifests differ" in item for item in result["errors"]))
        output.unlink()
        with self.assertRaises(gates.InputError):
            self.run_gate()

    def test_supervision_must_finish_empty(self) -> None:
        supervision = self.root / "run" / "supervision.log"
        supervision.write_text("fixture stop_group ERROR: process remains\n")
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("supervision" in item for item in result["errors"]))

    def test_snapshot_or_staged_binary_mutation_fails(self) -> None:
        self.checker_snapshot.write_text("changed checker bytes\n")
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("immutable snapshot" in item for item in result["errors"]))
        self.checker_snapshot.write_text("fixture check-tp2-sealed-gates.py.snapshot\n")

        self.native.write_bytes(b"changed native bytes")
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("staged file" in item for item in result["errors"]))

    def test_benchmark_freshness_and_suite_binding_fail_closed(self) -> None:
        bench_path = self.root / "data" / "bench.json"
        payload = json.loads(bench_path.read_text())
        payload["fresh_response_validity"]["cached_tokens_all_zero"] = False
        bench_path.write_text(json.dumps(payload))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("cached_tokens_all_zero" in item for item in result["errors"]))

        payload["fresh_response_validity"]["cached_tokens_all_zero"] = True
        payload["rows"][3]["prompt_id"] = "wrong-prompt"
        bench_path.write_text(json.dumps(payload))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("suite prompt identity" in item for item in result["errors"]))

        payload["rows"][3]["prompt_id"] = SUITE_PAYLOAD["prompts"][3]["id"]
        payload["run_identity"]["seed"] = 0
        bench_path.write_text(json.dumps(payload))
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(any("request identity" in item for item in result["errors"]))

    def test_inconsistent_expected_cardinality_is_input_error(self) -> None:
        self.args.expected_aot_loads = 2
        with self.assertRaises(gates.InputError):
            self.run_gate()

    def test_sync_after_model_forward_identity_is_fail_closed(self) -> None:
        self.args.expected_sync_after_model_forward = 1
        result, passed = self.run_gate()
        self.assertFalse(passed)
        self.assertTrue(
            any("sync_after_model_forward" in item for item in result["errors"])
        )

        identity = self.root / "run" / "identity.env"
        identity.write_text(
            identity.read_text()
            .replace("sync_after_model_forward=0\n", "sync_after_model_forward=1\n")
            .replace(
                "expected_sync_after_model_forward=0\n",
                "expected_sync_after_model_forward=1\n",
            )
        )
        result, passed = self.run_gate()
        self.assertTrue(passed, result)

    def test_quality_and_baseline_hash_are_fail_closed(self) -> None:
        baseline = self.baseline
        baseline_sha = hashlib.sha256(baseline.read_bytes()).hexdigest()
        identity = self.root / "run" / "identity.env"
        text = identity.read_text()
        text = text.replace(
            "quality_baseline_json=\n",
            f"quality_baseline_json={baseline}\n",
        ).replace(
            "quality_baseline_json_sha256=\n",
            f"quality_baseline_json_sha256={baseline_sha}\n",
        ).replace("run_quality=0\n", "run_quality=1\n")
        identity.write_text(text)
        summary = self.root / "run" / "summary.json"
        summary.write_text(
            json.dumps(
                {
                    "status": {"quality_rc": 0, "quality_skipped": False},
                    "quality_summary": {
                        "pass_all": True,
                        "baseline_match_all": True,
                    },
                }
            )
        )
        args = self.args
        args.require_quality_pass = True
        result, passed = gates.check_arm(args)
        self.assertTrue(passed, result)

        payload = json.loads(summary.read_text())
        payload["quality_summary"]["baseline_match_all"] = False
        summary.write_text(json.dumps(payload))
        result, passed = gates.check_arm(args)
        self.assertFalse(passed)
        self.assertTrue(any("quality gate" in item for item in result["errors"]))

    def test_duplicate_identity_is_input_error(self) -> None:
        identity = self.root / "run" / "identity.env"
        identity.write_text(identity.read_text() + "tensor_parallel_size=2\n")
        with self.assertRaises(gates.InputError):
            self.run_gate()


class ReplayMicroscopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "run").mkdir()
        (self.root / "run" / "server.stdout.log").write_text("fixture server log\n")
        self.trace = self.root / "replay-microscope.jsonl"
        self.identity = {
            "replay_microscope_required": "1",
            "replay_microscope_file": str(self.trace.resolve()),
            "replay_microscope_max_lines": "6",
            "replay_microscope_rank": "0",
            "replay_microscope_req_regex": gates.REPLAY_MICROSCOPE_REQ_REGEX,
            "replay_microscope_tensor_limit": "1",
            "replay_microscope_topk": "0",
            "replay_microscope_min_tokens_no_spec": "849",
            "replay_microscope_max_tokens_no_spec": "849",
        }
        rows = [
            {"key": (index, f"p{index}", f"{index + 1:064x}"), "token_ids": [index]}
            for index in range(25)
        ]
        rows[24] = {
            "key": (
                24,
                "holdout--long-rollover-repository-audit",
                "f" * 64,
            ),
            "token_ids": [71093, 13102],
        }
        self.bench = {"rows": rows}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_records(self, records: list[dict]) -> None:
        self.trace.write_text(
            "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records)
        )

    def test_exact_six_stage_trace_passes(self) -> None:
        self.write_records(replay_records())
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(errors, [], result)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["request_id"], TRACE_REQ_ID)
        self.assertEqual(result["sampled_token"], 71093)
        self.assertEqual(
            result["logits_after_compute"]["token_ids"], [71093, 13102]
        )
        self.assertEqual(
            result["logits_after_compute"]["top1_top2_margin"], 0.5
        )
        self.assertTrue(result["sampled_token_matches_bench"])

    def test_missing_stage_or_wrong_request_fails(self) -> None:
        records = replay_records()[:-1]
        records[0]["req_ids"] = ["unexpected"]
        records[0]["matched_req_ids"] = ["wrong"]
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("stages" in error for error in errors))
        self.assertTrue(any("unexpected request set" in error for error in errors))
        self.assertTrue(any("wrong request" in error for error in errors))

    def test_empty_required_tensor_fails(self) -> None:
        records = replay_records()
        records[0]["tensors"]["input_ids"]["numel"] = 0
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("required tensor" in error for error in errors))

    def test_boolean_integer_fields_fail(self) -> None:
        records = replay_records()
        records[0]["tp_rank"] = False
        records[1]["tensors"]["hidden_states"]["numel"] = True
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("tp_rank" in error for error in errors))
        self.assertTrue(any("required tensor" in error for error in errors))

    def test_nonstandard_constant_or_duplicate_key_is_malformed(self) -> None:
        self.trace.write_text('{"stage":"inputs","value":NaN}\n')
        with self.assertRaises(gates.InputError):
            gates.load_jsonl(self.trace)
        self.trace.write_text('{"stage":"inputs","stage":"inputs"}\n')
        with self.assertRaises(gates.InputError):
            gates.load_jsonl(self.trace)

    def test_unbound_logit_row_fails(self) -> None:
        records = replay_records()
        records[3]["logit_rows"][0]["req_id"] = "wrong"
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("top-2 logit evidence" in error for error in errors))

    def test_internal_request_suffix_and_consistency_are_required(self) -> None:
        records = replay_records()
        records[0]["req_ids"] = [gates.REPLAY_MICROSCOPE_REQ_BASE]
        records[0]["matched_req_ids"] = [gates.REPLAY_MICROSCOPE_REQ_BASE]
        records[0]["requests"][0]["req_id"] = gates.REPLAY_MICROSCOPE_REQ_BASE
        other_req_id = f"{gates.REPLAY_MICROSCOPE_REQ_BASE}-cafebabe"
        records[1]["req_ids"] = [other_req_id]
        records[1]["matched_req_ids"] = [other_req_id]
        records[1]["requests"][0]["req_id"] = other_req_id
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("unexpected request set" in error for error in errors))
        self.assertTrue(
            any("changed internal request ID" in error for error in errors)
        )

    def test_trace_error_field_fails_but_nonfinite_is_reported(self) -> None:
        records = replay_records()
        records[1]["tensors"]["hidden_states"]["error"] = "fixture"
        records[2]["logit_rows"] = [{"num_tokens_no_spec_cpu": "error:fixture"}]
        records[3]["tensors"]["logits"]["nan"] = 1
        self.write_records(records)
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertTrue(any("trace-error" in error for error in errors))
        self.assertIn(
            "$[2].logit_rows[0].num_tokens_no_spec_cpu",
            result["trace_error_paths"],
        )
        self.assertTrue(result["nonfinite_paths"])

    def test_sampled_bench_mismatch_is_scientific_data_not_malformed_trace(self) -> None:
        self.write_records(replay_records(sampled_token=0))
        result, errors = gates.validate_replay_microscope(
            self.root, self.identity, self.bench
        )
        self.assertEqual(errors, [], result)
        self.assertFalse(result["sampled_token_matches_bench"])


class ParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate.json"
        self.peer = self.root / "peer.json"
        self.reference = self.root / "reference.json"
        for path in (self.candidate, self.peer, self.reference):
            bench(path, [[1, 2, 3], [4, 5]])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def args(self, *, require_reference: bool = True) -> argparse.Namespace:
        return argparse.Namespace(
            candidate=str(self.candidate),
            peer=str(self.peer),
            expected_peer_sha256=gates.sha256_file(self.peer),
            reference=str(self.reference),
            expected_reference_sha256=gates.sha256_file(self.reference),
            require_reference_exact=require_reference,
        )

    def test_exact_peer_and_reference_pass(self) -> None:
        result, passed = gates.check_parity(self.args())
        self.assertTrue(passed, result)
        self.assertEqual(result["candidate_peer"]["exact_count"], 2)

    def test_token_flip_fails_even_with_same_output_sha(self) -> None:
        bench(self.candidate, [[1, 9, 3], [4, 5]])
        result, passed = gates.check_parity(self.args(require_reference=False))
        self.assertFalse(passed)
        difference = result["candidate_peer"]["differences"][0]["first_difference"]
        self.assertEqual(difference["index"], 1)
        self.assertEqual(difference["left_token"], 9)

    def test_length_difference_is_reported(self) -> None:
        bench(self.candidate, [[1, 2, 3, 8], [4, 5]])
        result, passed = gates.check_parity(self.args(require_reference=False))
        self.assertFalse(passed)
        difference = result["candidate_peer"]["differences"][0]["first_difference"]
        self.assertEqual(difference["index"], 3)
        self.assertEqual(difference["right_token"], None)

    def test_order_or_duplicate_identity_fails_closed(self) -> None:
        bench(self.candidate, [[1, 2, 3], [4, 5]], order=[1, 0])
        with self.assertRaises(gates.InputError):
            gates.check_parity(self.args(require_reference=False))

        data = json.loads(self.peer.read_text())
        data["rows"][1].update(data["rows"][0])
        self.peer.write_text(json.dumps(data))
        with self.assertRaises(gates.InputError):
            gates.check_parity(self.args(require_reference=False))

    def test_reference_mismatch_can_be_report_only_or_required(self) -> None:
        bench(self.reference, [[9, 2, 3], [4, 5]])
        result, passed = gates.check_parity(self.args(require_reference=False))
        self.assertTrue(passed, result)
        self.assertFalse(result["candidate_reference"]["all_exact"])
        result, passed = gates.check_parity(self.args(require_reference=True))
        self.assertFalse(passed)

    def test_peer_snapshot_hash_is_enforced(self) -> None:
        args = self.args()
        args.expected_peer_sha256 = "0" * 64
        with self.assertRaises(gates.InputError):
            gates.check_parity(args)


if __name__ == "__main__":
    unittest.main()

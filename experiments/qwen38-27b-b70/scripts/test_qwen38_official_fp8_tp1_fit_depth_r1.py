#!/usr/bin/env python3
"""Focused inert tests for the official FP8 TP1 bounded fit packet."""
import importlib.util,json,subprocess,sys,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
VERIFY_PATH=HERE/"verify-20260826-qwen38-official-fp8-tp1-fit-depth-r1.py"
RUN_PATH=HERE/"run-20260826-qwen38-official-fp8-tp1-fit-depth-r1.sh"

def load_verifier():
    spec=importlib.util.spec_from_file_location("qwen38_official_fp8_tp1_verifier_tested",VERIFY_PATH);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.verifier=load_verifier();cls.value,cls.manifest=cls.verifier.load_contract()
    def test_exact_revision_runtime_and_ladder(self):
        self.assertEqual(self.value["model"]["revision"],"017b9c7af6b5689d5dd426a76e0bc077eb5ca20a");self.assertEqual(self.value["model"]["target_path"],"/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7");self.assertEqual(self.value["runtime"]["image"],"vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f");self.assertEqual([row["active_context_tokens"] for row in self.value["fit_ladder"]],[8192,4096,2048]);self.assertEqual(len(self.manifest["lfs_files"]),66);self.assertEqual(sum(row["bytes"] for row in self.manifest["lfs_files"]),30866866928)
    def test_inert_readiness_and_no_download(self):
        before={path.name:(path.stat().st_size,path.stat().st_mtime_ns) for path in self.verifier.TARGET.iterdir()} if self.verifier.TARGET.is_dir() else {}
        result=subprocess.run([sys.executable,"-B",str(VERIFY_PATH)],text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);plan=json.loads(result.stdout);self.assertEqual(plan["gpu_actions"],0);self.assertEqual(plan["network_actions"],0);self.assertEqual(plan["download_actions"],0);self.assertEqual(plan["verification_actions"],0);self.assertEqual(plan["readiness"]["expected_files"],66)
        after={path.name:(path.stat().st_size,path.stat().st_mtime_ns) for path in self.verifier.TARGET.iterdir()} if self.verifier.TARGET.is_dir() else {};self.assertEqual(before,after)
        source=VERIFY_PATH.read_text()+RUN_PATH.read_text();self.assertNotIn("snapshot_download",source);self.assertNotIn("huggingface-cli",source);self.assertNotIn("hf download",source);self.assertNotIn("docker pull",source)
    def test_explicit_verification_refuses_incomplete_before_hashing(self):
        ready=self.verifier.readiness(self.manifest)
        if not ready["ready_for_full_verification"]:
            result=subprocess.run([sys.executable,"-B",str(VERIFY_PATH),"--verify"],text=True,capture_output=True,timeout=10);self.assertNotEqual(result.returncode,0);self.assertIn("model download is incomplete",result.stderr)
        source=VERIFY_PATH.read_text();self.assertIn("BASE.hash_direct",source);self.assertIn("BASE.hash_ordinary",source);self.assertNotIn("hash_bypassing_cache",source)
    def test_runner_default_is_inert_and_failure_policy_frozen(self):
        result=subprocess.run(["bash",str(RUN_PATH)],text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);plan=json.loads(result.stdout);self.assertEqual(plan["gpu_actions"],0);self.assertEqual(plan["download_actions"],0)
        publication=self.value["publication"];self.assertEqual(publication["valid_cells_if_8k_fits"],3);self.assertEqual(publication["valid_cells_if_4k_fits"],2);self.assertEqual(publication["valid_cells_if_only_2k_fits"],1);self.assertFalse(publication["headline_or_protected_replacement"]);self.assertEqual(publication["protected_decode_values"],[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144])

if __name__=="__main__":unittest.main()

import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("summarize_onednn_verbose.py")
SPEC = importlib.util.spec_from_file_location("summarize_onednn_verbose", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OneDnnVerboseSummaryTests(unittest.TestCase):
    def test_ignores_pre_marker_and_ranks_post_marker_groups(self) -> None:
        prefix = "onednn_verbose,v1,primitive,exec,gpu:0,matmul,jit:gemm:any,undef,x,a,,"
        with tempfile.TemporaryDirectory() as temp:
            log = pathlib.Path(temp) / "server.log"
            log.write_text(
                prefix + "pre,100\n"
                + "slot launch_slot_: processing task\n"
                + prefix + "large,3\n"
                + prefix + "large,2\n"
                + prefix + "small,1\n"
            )
            result = MODULE.summarize(log, "processing task", 5)
        self.assertEqual(result["exec_records"], 3)
        device = result["devices"]["gpu:0"]
        self.assertEqual(device["summed_primitive_duration_ms"], 6)
        self.assertEqual(device["top_groups"][0]["problem"], "large")
        self.assertEqual(device["top_groups"][0]["calls"], 2)
        self.assertAlmostEqual(device["top_groups"][0]["share_percent"], 100 * 5 / 6)


if __name__ == "__main__":
    unittest.main()

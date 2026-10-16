"""CPU-only scope/dispatch tests: no runtime, torch or device import."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

import trace_marks as marks


class MarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.active = self.root / "active"
        self.itt = Mock()
        self.context = NS(attn_metadata={"gdn": NS(num_prefills=0, num_spec_decodes=1, num_spec_decode_tokens=2)})
        self.marker = marks.Marker(self.active, self.root, self.itt, lambda: 2,
                                   lambda: self.context, {"test": "pin"})

    def test_inactive_does_not_inspect_shape_or_rank(self):
        self.marker.get_rank = Mock(side_effect=AssertionError)
        with self.marker.scope("target", None):
            pass
        self.itt.rangePush.assert_not_called()

    def test_exact_verify_marker_and_rank_receipt(self):
        self.active.touch()
        with self.marker.scope("target", 2):
            pass
        self.itt.rangePush.assert_called_once_with("A367|verify|M=2|seq=1")
        receipt = json.loads(next(self.root.glob("marker-rank-2-pid-*.json")).read_text())
        self.assertEqual(receipt["rank"], 2)
        self.assertEqual(receipt["source_pins"], {"test": "pin"})

    def test_m2_prefill_is_not_verify(self):
        self.active.touch()
        self.context.attn_metadata["gdn"].num_prefills = 1
        with self.marker.scope("target", 2):
            pass
        self.itt.rangePush.assert_called_once_with("A367|target|M=2|seq=1")

    def test_missing_metadata_is_not_verify(self):
        self.assertFalse(marks.is_verify(2, NS(attn_metadata={})))
        self.assertFalse(marks.is_verify(2, None))
        self.assertFalse(marks.is_verify(1, self.context))

    def test_nested_scope_emits_once(self):
        self.active.touch()
        with self.marker.scope("draft", 1):
            with self.marker.scope("target", 2):
                pass
        self.itt.rangePush.assert_called_once_with("A367|draft|M=1|seq=1")
        self.itt.rangePop.assert_called_once()

    def test_exception_closes_scope_and_next_scope_works(self):
        self.active.touch()
        with self.assertRaises(ValueError):
            with self.marker.scope("draft", 1):
                raise ValueError("test")
        with self.marker.scope("draft", 1):
            pass
        self.assertEqual(self.itt.rangePop.call_count, 2)
        self.assertEqual(self.itt.rangePush.call_args.args, ("A367|draft|M=1|seq=2",))

    def test_shape_failure_is_closed(self):
        self.active.touch()
        with self.assertRaisesRegex(RuntimeError, "row count"):
            with self.marker.scope("target", None):
                pass

    def test_uninitialized_rank_is_closed(self):
        self.active.touch()
        self.marker.get_rank = lambda: None
        with self.assertRaisesRegex(RuntimeError, "initialized rank"):
            with self.marker.scope("target", 2):
                pass

    def test_rows_does_not_read_tensor_contents(self):
        class Tensor:
            shape = (2, 2560)
            def __int__(self):
                raise AssertionError("tensor contents read")
            def item(self):
                raise AssertionError("tensor contents read")
        self.assertEqual(marks.rows(Tensor()), 2)
        self.assertIsNone(marks.rows(NS(shape=())))
        self.assertIsNone(marks.rows(NS(shape=(0,))))

    def test_positions_metadata_when_ids_absent(self):
        self.assertEqual(marks.call_rows((None, NS(shape=(2,))), {}), 2)
        self.assertEqual(marks.call_rows((), {"positions": NS(shape=(3, 2))}), 2)

    def test_forward_returns_original_object_and_arguments(self):
        self.active.touch()
        result = object()
        seen = []
        class Target:
            def forward(self, *args, **kwargs):
                seen.append((args, kwargs))
                return result
        marks.patch_forward(Target, self.marker, "target")
        tensor = NS(shape=(2,))
        self.assertIs(Target().forward(tensor, preserve="yes"), result)
        self.assertEqual(seen, [((tensor,), {"preserve": "yes"})])

    def test_graph_wrapper_marks_replay_without_forward_call(self):
        self.active.touch()
        target = type("Qwen4ExpForConditionalGeneration", (), {"__module__": "vllm.models.qwen4_exp.amd.model"})()
        result = object()
        class Graph:
            runnable = target
            def __call__(self, *args, **kwargs):
                return result  # Simulates replay: target.forward is never entered.
        marks.patch_graph(Graph, self.marker)
        self.assertIs(Graph()(input_ids=NS(shape=(2,))), result)
        self.itt.rangePush.assert_called_once_with("A367|verify|M=2|seq=1")

    def test_unknown_graph_runnable_fails_closed(self):
        self.active.touch()
        class Graph:
            runnable = object()
            def __call__(self, *args, **kwargs):
                raise AssertionError("unclassified graph executed")
        marks.patch_graph(Graph, self.marker)
        with self.assertRaisesRegex(RuntimeError, "classify"):
            Graph()(NS(shape=(2,)))

    def test_proposer_scope_labels_batch_not_model_rows(self):
        self.active.touch()
        result = object()
        class Proposer:
            def propose(self, target_token_ids, next_token_ids):
                return result
        marks.patch_proposer(Proposer, self.marker)
        self.assertIs(Proposer().propose(NS(shape=(2,)), NS(shape=(1,))), result)
        self.itt.rangePush.assert_called_once_with("A367|draft|B=1|seq=1")

    def test_batch_dimension_rejected_for_target(self):
        self.active.touch()
        with self.assertRaisesRegex(RuntimeError, "dimension"):
            with self.marker.scope("target", 2, dimension="B"):
                pass

    def test_unknown_wrapper_does_not_inherit_known_runnable_identity(self):
        target = type("Qwen4ExpForConditionalGeneration", (), {"__module__": "vllm.models.qwen4_exp.amd.model"})()
        self.assertIsNone(marks.runnable_phase(NS(runnable=target)))
        known = type("CUDAGraphWrapper", (), {"__module__": "vllm.compilation.cuda_graph"})()
        known.runnable = target
        self.assertEqual(marks.runnable_phase(known), "target")

    def test_scope_stops_after_active_removed(self):
        self.active.touch()
        with self.marker.scope("draft", 1):
            pass
        self.active.unlink()
        with self.marker.scope("draft", 1):
            pass
        self.assertEqual(self.itt.rangePush.call_count, 1)

    def test_source_pins_cover_graph_target_and_draft(self):
        self.assertIn("vllm/compilation/cuda_graph.py", marks.SOURCE_PINS)
        self.assertIn("vllm/models/qwen4_exp/amd/model.py", marks.SOURCE_PINS)
        self.assertIn("vllm/v1/spec_decode/llm_base_proposer.py", marks.SOURCE_PINS)
        self.assertTrue(all(len(v) == 64 for v in marks.SOURCE_PINS.values()))


if __name__ == "__main__":
    unittest.main()

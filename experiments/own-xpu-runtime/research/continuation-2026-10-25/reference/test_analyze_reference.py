import copy
import math
from pathlib import Path
import unittest

import analyze_reference as audit


class RowValidation(unittest.TestCase):
    def setUp(self):
        self.inp={"tokens":[10,11,12,13],"score_from":2}
        self.rows=[{"position":1,"argmax":12,"top":[[12,4,0]],"next":12,"next_logit":4},
                   {"position":2,"argmax":14,"top":[[14,5,0],[13,4.9,0]],"next":13,"next_logit":4.9},
                   {"position":3,"argmax":99,"top":[[99,5,0]]}]

    def test_absolute_position_and_terminal_row(self):
        result=audit.analyze_rows(self.inp,self.rows)
        self.assertEqual(result["scored_positions"],2)
        self.assertEqual(len(result["disagreements"]),1)
        self.assertEqual(result["disagreements"][0]["output_index"],1)

    def test_wrong_teacher_forced_token_fails(self):
        self.rows[1]["next"]=12
        with self.assertRaisesRegex(ValueError,"next token"):
            audit.analyze_rows(self.inp,self.rows)

    def test_missing_position_fails(self):
        with self.assertRaisesRegex(ValueError,"position"):
            audit.analyze_rows(self.inp,self.rows[1:])

    def test_terminal_prediction_is_not_a_score(self):
        self.rows[-1]["next"]=100
        with self.assertRaisesRegex(ValueError,"terminal"):
            audit.analyze_rows(self.inp,self.rows)

    def test_control_requires_identical_prefix(self):
        other=copy.deepcopy(self.rows);other[0]["next"]=99
        with self.assertRaisesRegex(ValueError,"teacher-forced"):
            audit.compare_rows(self.rows,other)

    def test_capture_writer_geometry_and_size(self):
        layout=audit.capture_layout()
        self.assertEqual(layout["float_values"],2048)
        self.assertEqual(layout["bytes"],8192)
        self.assertEqual(layout["max_byte_offset"],8191)
        with self.assertRaisesRegex(ValueError,"dimensions"):
            audit.capture_layout(value_heads=47)


class ActualOperatorWitnesses(unittest.TestCase):
    @unittest.skipUnless(Path("/dev/shm/llref/build/ggml/src/libggml-cpu.a").is_file()
                         and (audit.HERE/"frozen-gdn-state.f32").is_file(),
                         "run analyzer first to extract archived operator fixtures; retained CPU library required")
    def test_fused_update_and_dot_preserve_exact_product_residual(self):
        output=audit.operator_probe(Path("/dev/shm/llref"),audit.HERE/"frozen-embedding.f32")
        # (1-2^-23)*(1+2^-23)-1 is exactly -2^-46. Two rounded
        # operations lose it; fused multiplication/addition retains it.
        for name in ("state_update","dot_fma_witness"):
            result=output["gdn_fixed"][name]
            self.assertEqual(result["native"],0)
            self.assertTrue(math.isclose(result["cpu"],-2**-46,rel_tol=1e-8))
        frozen=output["rms_frozen_embedding"]
        self.assertNotEqual(frozen["mean"]["native_bits"],frozen["mean"]["cpu_bits"])
        self.assertEqual(frozen["normalized_values_differ"],0)
        self.assertEqual(output["rms_fixed"]["normalized_values_differ"],2560)
        gdn=output["gdn_query_normalization_frozen"]
        self.assertEqual(gdn["values_differ"],38)
        # With identical sum, the alternative algebra still changes all of the
        # differing values: this isolates normalization arithmetic, not input drift.
        self.assertEqual(gdn["formula_only_values_differ"],38)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("sync-public-result-summary.py")
SPEC = importlib.util.spec_from_file_location("sync_public_result_summary", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublicResultSummaryTests(unittest.TestCase):
    def test_readme_summary_is_current_and_complete(self) -> None:
        readme = MODULE.README.read_text(encoding="utf-8")
        block = readme.split(MODULE.START, 1)[1].split(MODULE.END, 1)[0]
        self.assertEqual(MODULE.update(check=True), 0)

        catalog = json.loads(MODULE.CATALOG.read_text(encoding="utf-8"))
        for package in catalog["packages"]:
            with self.subTest(package=package["id"]):
                value = package["library"]["featured_metric"]["value"]
                self.assertIn(f"models/{package['id']}.html", block)
                self.assertIn(MODULE.format_value(float(value)), block)

    def test_qwen_fp8_selected_and_negative_values_are_not_conflated(self) -> None:
        readme = MODULE.README.read_text(encoding="utf-8")
        block = readme.split(MODULE.START, 1)[1].split(MODULE.END, 1)[0]
        homepage = (MODULE.ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("58.391033", block)
        self.assertNotIn("158.60211", block)
        self.assertIn(">58.39&dagger;</a>", homepage)
        self.assertIn("high-acceptance 40-token fixture", homepage)
        self.assertIn(">1,094.3&dagger;</a>", homepage)
        self.assertNotIn("Our fastest Qwen3.8 experiment", homepage)


if __name__ == "__main__":
    unittest.main()

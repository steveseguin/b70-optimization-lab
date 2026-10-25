"""CPU-only source provenance, closure and reproducibility checks."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("source_bundle", Path(__file__).with_name("source_bundle.py"))
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = self.root / "engine"
        (self.engine / "src").mkdir(parents=True)
        self.write("README.md", "Research only\n")
        self.write("build.py", "# compile entrypoint\n")
        self.write("src/main.cpp", '#include "local.hpp"\n#include <vector>\n')
        self.write("src/local.hpp", "#pragma once\n")
        self.manifest = {"compiler": "/opt/intel/oneapi/compiler/2026.0/bin/icpx",
                         "base_binary": "/home/example/private-engine",
                         "files": {"main.cpp": {}, "local.hpp": {}},
                         "assets": {},
                         "translation_units": [{"source": "main.cpp", "object": "main.o",
                                                "flags": ["-std=gnu++20", "-fsycl"],
                                                "original_object": "/mnt/old/private.o"}],
                         "link": {"compiler": "/opt/intel/oneapi/compiler/2026.0/bin/icpx",
                                  "flags": ["-fsycl", "-lcrypto", "-lze_loader"]}}
        self.save_manifest()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Source bundle test")
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, name, text):
        (self.engine / name).write_text(text)

    def save_manifest(self):
        self.write("build-manifest.json", json.dumps(self.manifest))

    def commit(self):
        self.git("add", "engine")
        self.git("commit", "-qm", "Fixture inputs")

    def test_deterministic_bytes_and_complete_hash_bound_payload(self):
        contents, report = bundle.prepare(self.engine)
        first = bundle.archive_bytes(contents)
        (self.engine / "src/main.cpp").touch()
        second_contents, second_report = bundle.prepare(self.engine)
        self.assertEqual(first, bundle.archive_bytes(second_contents))
        self.assertEqual(report, second_report)
        self.assertEqual(report["source_commit"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertEqual(report["include_edges"], [{"from": "main.cpp", "to": "local.hpp"}])
        self.assertEqual(report["external_system_headers"], ["vector"])
        self.assertFalse(report["validation"]["runtime_smoke"])
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:gz") as archive:
            members = archive.getmembers()
            self.assertTrue(all(member.isfile() and member.mtime == 0 and member.uid == 0 for member in members))
            for row in report["files"]:
                payload = archive.extractfile("own-xpu-runtime-source/" + row["path"]).read()
                self.assertEqual(bundle.digest(payload), row["sha256"])
        generated = json.loads(contents["build-manifest.json"])
        self.assertNotIn("base_binary", generated)
        self.assertNotIn("original_object", generated["translation_units"][0])
        self.assertEqual(generated["translation_units"][0]["flags"], self.manifest["translation_units"][0]["flags"])

    def test_missing_tracked_source_refused(self):
        (self.engine / "src/local.hpp").unlink()
        with self.assertRaisesRegex(bundle.BundleError, "Missing or non-regular"):
            bundle.prepare(self.engine)

    def test_untracked_header_cannot_close_committed_include(self):
        self.write("src/main.cpp", '#include "untracked.hpp"\n')
        self.commit()
        self.write("src/untracked.hpp", "// not a public input\n")
        with self.assertRaisesRegex(bundle.BundleError, "Untracked include"):
            bundle.prepare(self.engine)

    def test_missing_local_include_refused(self):
        self.write("src/main.cpp", '#include "missing.hpp"\n')
        self.commit()
        with self.assertRaisesRegex(bundle.BundleError, "Missing local include"):
            bundle.prepare(self.engine)

    def test_unknown_angle_header_cannot_be_classified_as_system(self):
        self.write("src/main.cpp", '#include <missing-project.hpp>\n')
        self.commit()
        with self.assertRaisesRegex(bundle.BundleError, "Unknown angle include"):
            bundle.prepare(self.engine)

    def test_supplemental_host_header_is_committed_and_hash_bound(self):
        path = self.root / "gsq-rco-iq3s/integration/host-support/device_validation.hpp"
        path.parent.mkdir(parents=True)
        path.write_text("#pragma once\n")
        self.write("src/main.cpp", "#include <device_validation.hpp>\n")
        self.git("add", path.relative_to(self.root).as_posix())
        self.commit()
        contents, report = bundle.prepare(self.engine)
        self.assertEqual(contents["src/device_validation.hpp"], path.read_bytes())
        self.assertEqual(report["supplemental_source_inputs"][0]["input"], path.relative_to(self.root).as_posix())
        self.assertNotIn("device_validation.hpp", report["external_system_headers"])
        path.write_text("// modified\n")
        with self.assertRaisesRegex(bundle.BundleError, "changed supplemental"):
            bundle.prepare(self.engine)

    def test_missing_manifest_source_refused_even_if_not_included(self):
        self.manifest["files"]["not-tracked.hpp"] = {}
        self.save_manifest()
        self.commit()
        with self.assertRaisesRegex(bundle.BundleError, "Missing/untracked declared"):
            bundle.prepare(self.engine)

    def test_dirty_source_cannot_claim_commit_identity(self):
        self.write("src/local.hpp", "// uncommitted edit\n")
        with self.assertRaisesRegex(bundle.BundleError, "differs from source_commit"):
            bundle.prepare(self.engine)

    def test_symlink_source_refused(self):
        (self.engine / "src/local.hpp").unlink()
        (self.engine / "src/local.hpp").symlink_to("main.cpp")
        with self.assertRaisesRegex(bundle.BundleError, "non-regular"):
            bundle.prepare(self.engine)

    def test_nonliteral_include_refused(self):
        self.write("src/main.cpp", "#include HEADER_MACRO\n")
        self.commit()
        with self.assertRaisesRegex(bundle.BundleError, "Nonliteral"):
            bundle.prepare(self.engine)

    def test_tracked_optional_planning_included_untracked_omitted(self):
        (self.engine / "planning").mkdir()
        self.write("planning/README.md", "Not runtime qualified\n")
        self.commit()
        self.write("planning/local-notes.md", "Untracked\n")
        contents, _ = bundle.prepare(self.engine)
        self.assertIn("planning/README.md", contents)
        self.assertNotIn("planning/local-notes.md", contents)

    def test_portable_profile_and_build_helper_are_included(self):
        (self.engine / "deployment").mkdir()
        (self.engine / "profiles").mkdir()
        self.write("build.py", "from deployment.prepare import require\n")
        self.write("deployment/prepare.py", "# deployment helper\n")
        self.write("deployment/bound.hpp.in", "# authority template\n")
        self.write("profiles/profile.json", '{"portable":true}\n')
        self.commit()
        contents, _ = bundle.prepare(self.engine)
        self.assertIn("deployment/prepare.py", contents)
        self.assertIn("deployment/bound.hpp.in", contents)
        self.assertIn("profiles/profile.json", contents)

    def test_untracked_build_helper_refused(self):
        self.write("build.py", "from deployment.prepare import require\n")
        self.commit()
        (self.engine / "deployment").mkdir()
        self.write("deployment/prepare.py", "# not committed\n")
        self.write("deployment/bound.hpp.in", "# not committed\n")
        with self.assertRaisesRegex(bundle.BundleError, "Untracked required input"):
            bundle.prepare(self.engine)


if __name__ == "__main__":
    unittest.main()

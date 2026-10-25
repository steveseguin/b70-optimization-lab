"""CPU-only source provenance, closure and reproducibility checks."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
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



class PythonClosureTests(unittest.TestCase):
    setUp=SourceBundleTests.setUp
    git=SourceBundleTests.git
    write=SourceBundleTests.write
    save_manifest=SourceBundleTests.save_manifest
    commit=SourceBundleTests.commit
    def install_live_fixture(self):
        (self.engine/'deployment').mkdir(exist_ok=True)
        self.write('deployment/portable_live.py','import live_wavefront_driver\n')
        for name in bundle.PORTABLE_LIVE_RUNTIME:
            path=self.engine/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('# runtime fixture\n')
        self.write('tools/live_wavefront_driver.py','import wavefront_driver\nfrom persistent_live_suite import helper\n')
        self.write('tools/wavefront_driver.py','import pipeline_driver\n')
        self.write('tools/persistent_wavefront_driver.py','import persistent_live_suite\n')
    def test_explicit_runtime_and_lazy_import_closure_exported(self):
        self.install_live_fixture();self.commit()
        contents,report=bundle.prepare(self.engine)
        self.assertTrue(all(name in contents for name in bundle.PORTABLE_LIVE_RUNTIME))
        self.assertTrue(report['validation']['literal_python_import_closure'])
        self.assertIn(dict(**{'from':'tools/live_wavefront_driver.py','to':'tools/persistent_live_suite.py'}),report['python_import_edges'])
        self.assertEqual(bundle.archive_bytes(contents),bundle.archive_bytes(bundle.prepare(self.engine)[0]))
    def test_untracked_lazy_runtime_refuses_complete_bundle_claim(self):
        self.install_live_fixture()
        lazy=self.engine/'tools/persistent_live_suite.py';raw=lazy.read_bytes();lazy.unlink();self.commit();lazy.write_bytes(raw)
        with self.assertRaisesRegex(bundle.BundleError,'Untracked required input'):
            bundle.prepare(self.engine)
    def test_new_untracked_python_import_refused(self):
        self.install_live_fixture();self.write('tools/pipeline_driver.py','import untracked_local_helper\n');self.commit()
        self.write('tools/untracked_local_helper.py','# not tracked\n')
        with self.assertRaisesRegex(bundle.BundleError,'Missing/untracked Python dependency'):
            bundle.prepare(self.engine)
    def test_unknown_external_package_not_silently_system(self):
        self.write('build.py','import external_package_not_in_stdlib\n');self.commit()
        with self.assertRaisesRegex(bundle.BundleError,'Missing/untracked Python dependency'):
            bundle.prepare(self.engine)

    def install_rolling_fixture(self):
        for name in bundle.ROLLING_RUNTIME:
            path=self.engine/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('# committed runtime fixture\n')
        self.write('planning/rolling_provider/arbiter.py','CAPACITY=2\n')
        self.write('planning/rolling_provider/coordinator.py','from .arbiter import CAPACITY\n')
        self.write('planning/rolling_provider/transport.py',
            'from .coordinator import CAPACITY\nimport pending_ring_live_driver\n')
        self.write('tools/rolling_ring_driver.py','from rolling_provider import transport\n')
        self.write('tools/pending_ring_live_driver.py','import ring_live_driver\n')
        self.write('tools/ring_live_driver.py','import ring_driver\n')
        self.write('tools/ring_driver.py','import wavefront_driver\nimport ring_wire\n')
        self.write('tools/ring_wire.py','import ring_coordinator\n')

    def test_complete_rolling_package_extracts_imports_and_is_deterministic(self):
        self.install_rolling_fixture();self.commit()
        contents,report=bundle.prepare(self.engine)
        self.assertTrue(set(bundle.ROLLING_RUNTIME)<=set(contents))
        self.assertTrue(set(bundle.ROLLING_RUNTIME)<=set(report['explicit_dynamic_python_dependencies']))
        first=bundle.archive_bytes(contents)
        self.assertEqual(first,bundle.archive_bytes(bundle.prepare(self.engine)[0]))
        extracted=self.root/'extracted';extracted.mkdir()
        with tarfile.open(fileobj=io.BytesIO(first),mode='r:gz') as archive:
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                target=extracted/member.name
                self.assertTrue(target.resolve().is_relative_to(extracted))
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
        snapshot=extracted/'own-xpu-runtime-source'
        code='import sys;sys.path[:0]=sys.argv[1:];import rolling_ring_driver;assert rolling_ring_driver.transport.CAPACITY==2'
        subprocess.run([sys.executable,'-I','-c',code,str(snapshot/'tools'),str(snapshot/'planning')],
                       check=True,capture_output=True,text=True,timeout=10)

    def test_untracked_rolling_package_member_cannot_claim_complete_runtime(self):
        self.install_rolling_fixture()
        missing=self.engine/'planning/rolling_provider/transport.py';raw=missing.read_bytes()
        missing.unlink();self.commit();missing.write_bytes(raw)
        with self.assertRaisesRegex(bundle.BundleError,'Untracked required input'):
            bundle.prepare(self.engine)

    def test_new_untracked_relative_package_dependency_is_refused(self):
        self.install_rolling_fixture()
        self.write('planning/rolling_provider/coordinator.py','from .untracked_helper import CAPACITY\n')
        self.commit();self.write('planning/rolling_provider/untracked_helper.py','CAPACITY=2\n')
        with self.assertRaisesRegex(bundle.BundleError,'Missing/untracked Python dependency'):
            bundle.prepare(self.engine)

    def test_planning_cpu_fixture_import_included_only_when_committed(self):
        self.install_rolling_fixture()
        self.write('planning/review.py','from test_ring_live_driver import helper\n')
        self.write('tools/test_ring_live_driver.py','helper=1\n')
        self.commit()
        contents,_=bundle.prepare(self.engine)
        self.assertIn('tools/test_ring_live_driver.py',contents)
        self.write('planning/review.py','from test_ring_live_wire import helper\n')
        self.commit();self.write('tools/test_ring_live_wire.py','helper=2\n')
        with self.assertRaisesRegex(bundle.BundleError,'Missing/untracked Python dependency'):
            bundle.prepare(self.engine)

if __name__ == "__main__":
    unittest.main()

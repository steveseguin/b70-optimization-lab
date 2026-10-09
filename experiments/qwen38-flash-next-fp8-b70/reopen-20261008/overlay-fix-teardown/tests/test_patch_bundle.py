"""Apply only to disposable CPU files; never touch installed/active runtime."""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
BASE=HERE.parent

class BundleTests(unittest.TestCase):
    def test_patch_matches_copies_and_closed_package_hashes(self):
        subprocess.run(['python3','-B',str(HERE/'build_patch.py'),'--check'],check=True,capture_output=True)
        manifest=json.loads((BASE/'overlay-manifest.json').read_text())
        with tempfile.TemporaryDirectory(prefix='flashnext-teardown-apply-') as temp:
            dest=Path(temp)
            files=set(manifest['support_files'])|{'overlay-manifest.json','screen.py','memory_watchdog.py'}
            files.update('overlay/'+p for p in manifest['files'])
            for rel in files:
                (dest/rel).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(BASE/rel,dest/rel)
            subprocess.run(['git','apply','--check',str(HERE/'teardown.patch')],cwd=dest,check=True,capture_output=True)
            subprocess.run(['git','apply',str(HERE/'teardown.patch')],cwd=dest,check=True,capture_output=True)
            for path in (HERE/'copies').rglob('*'):
                if path.is_file():self.assertEqual(path.read_bytes(),(dest/path.relative_to(HERE/'copies')).read_bytes())
            spec=importlib.util.spec_from_file_location('fixture_overlay',BASE/'apply_overlay.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            verified=module.verify_package(dest)
            self.assertIn('vllm/screen1b_teardown.py',verified['files'])
            self.assertIn('teardown_receipts.py',verified['support_files'])

    def test_modified_python_and_shell_parse(self):
        for path in (HERE/'copies').rglob('*.py'):
            ast.parse(path.read_text(),filename=str(path))
        subprocess.run(['bash','-n',str(HERE/'copies/container-entrypoint.sh')],check=True)

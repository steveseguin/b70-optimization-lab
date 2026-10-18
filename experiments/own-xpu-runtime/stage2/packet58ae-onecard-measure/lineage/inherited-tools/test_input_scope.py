import json
from pathlib import Path
import tempfile
import unittest
from input_scope import P, ROOT, check_pins, allowed_inputs


class InputScope(unittest.TestCase):
    def test_local(self):
        check_pins(ROOT, {str((P/'compare_bracket.py').relative_to(ROOT)): '0'*64})

    def test_sibling_mutable_even_with_valid_hash(self):
        for name in ('packet58w-onecard-record/verify_ready.py', 'packet58v-async-cache/window.py'):
            with self.assertRaisesRegex(ValueError, 'external mutable'):
                check_pins(ROOT, {str((P.parent/name).relative_to(ROOT)): '0'*64})

    def test_exact_allowlist_hash(self):
        name, digest = next(iter(allowed_inputs().items()))
        check_pins(ROOT, {name: digest})
        with self.assertRaisesRegex(ValueError, 'external mutable'):
            check_pins(ROOT, {name: '0'*64})

    def test_traversal_and_absolute(self):
        for name in ('../packet58w-onecard-record/verify_ready.py', str(P/'views.py')):
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                check_pins(P, {name: '0'*64})

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory(dir=P) as directory:
            path = Path(directory)/'escape'
            path.symlink_to(ROOT/'README.md')
            with self.assertRaisesRegex(ValueError, 'external mutable'):
                check_pins(P, {str(path.relative_to(P)): '0'*64})

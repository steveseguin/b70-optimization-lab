"""Temporary-file evidence limits; no native execution or operational paths."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bounded_evidence import BoundedEvidence, EvidenceLimit, EvidenceRefusal


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def writer(self, **kwargs):
        obj = BoundedEvidence(self.root, total_limit_bytes=kwargs.pop('total_limit_bytes', 10), **kwargs)
        self.addCleanup(obj.close)
        return obj

    def test_exact_limit_and_overflow_preserve_bytes_and_halt(self):
        w = self.writer();w.create('guard.jsonl', limit_bytes=5)
        self.assertEqual(w.append('guard.jsonl', b'12345'), 5)
        with self.assertRaises(EvidenceLimit):w.append('guard.jsonl', b'6')
        self.assertEqual((self.root/'guard.jsonl').read_bytes(), b'12345')
        self.assertTrue(w.status()['halted'])
        with self.assertRaises(EvidenceLimit):w.append('guard.jsonl', b'')

    def test_aggregate_limit_applies_across_files(self):
        w=self.writer();w.create('a',limit_bytes=10);w.create('b',limit_bytes=10)
        w.append('a',b'123456');w.append('b',b'7890')
        with self.assertRaises(EvidenceLimit):w.append('b',b'x')
        self.assertEqual(w.status()['payload_bytes'],10)
        self.assertEqual((self.root/'b').read_bytes(),b'7890')

    def test_existing_file_and_symlink_are_never_adopted(self):
        (self.root/'old').write_bytes(b'keep')
        w=self.writer()
        with self.assertRaises(FileExistsError):w.create('old',limit_bytes=8)
        self.assertEqual((self.root/'old').read_bytes(),b'keep')
        (self.root/'link').symlink_to(self.root/'missing')
        other=self.writer()
        with self.assertRaises(FileExistsError):other.create('link',limit_bytes=8)
        self.assertTrue((self.root/'link').is_symlink())

    def test_partial_write_then_error_charges_prefix_and_never_retries(self):
        w=self.writer();w.create('a',limit_bytes=10);real=os.write;calls=[]
        def partial(fd,data):
            calls.append(1)
            if len(calls)==1:return real(fd,data[:2])
            raise OSError('injected full disk')
        with patch('bounded_evidence.os.write',side_effect=partial):
            with self.assertRaisesRegex(OSError,'full disk'):w.append('a',b'12345')
        self.assertEqual((self.root/'a').read_bytes(),b'12')
        self.assertEqual(w.status()['payload_bytes'],2)
        with self.assertRaisesRegex(OSError,'full disk'):w.append('a',b'x')

    def test_external_replacement_does_not_receive_append(self):
        w=self.writer();w.create('a',limit_bytes=10);w.append('a',b'own')
        (self.root/'a').rename(self.root/'retained')
        (self.root/'a').write_bytes(b'foreign')
        with self.assertRaises(EvidenceRefusal):w.append('a',b'x')
        self.assertEqual((self.root/'a').read_bytes(),b'foreign')
        self.assertEqual((self.root/'retained').read_bytes(),b'own')

    def test_path_traversal_and_file_count_refuse(self):
        w=self.writer()
        with self.assertRaises(EvidenceRefusal):w.create('../escape',limit_bytes=1)
        other=self.writer(max_files=1);other.create('one',limit_bytes=1)
        with self.assertRaises(EvidenceLimit):other.create('two',limit_bytes=1)
        self.assertFalse((self.root/'two').exists())

    def test_nonprivate_root_and_closed_writer_refuse(self):
        os.chmod(self.root,0o755)
        with self.assertRaises(EvidenceRefusal):self.writer()
        os.chmod(self.root,0o700)
        w=self.writer();w.create('a',limit_bytes=3);w.close();w.close()
        with self.assertRaises(EvidenceRefusal):w.append('a',b'x')

    def test_external_append_is_detected_without_deleting_evidence(self):
        w=self.writer();w.create('a',limit_bytes=10);w.append('a',b'own')
        with (self.root/'a').open('ab') as out:out.write(b'other')
        with self.assertRaises(EvidenceRefusal):w.append('a',b'x')
        self.assertEqual((self.root/'a').read_bytes(),b'ownother')


if __name__ == '__main__':unittest.main(verbosity=2)

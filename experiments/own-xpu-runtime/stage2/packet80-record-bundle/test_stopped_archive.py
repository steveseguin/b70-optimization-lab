"""A packet80 chain freezes selection; historical packets never grant reuse."""
from pathlib import Path
import tempfile,unittest
import stopped_archive as archive
class StoppedArchive(unittest.TestCase):
    def test_new_packet_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:archive.require_fresh_chain(Path(tmp))
    def test_started_or_stopped_chain_refused(self):
        for name in ('device-cards01-a','device-cards01-a-stopped','device-cards01-b'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/name).mkdir();(root/name/'STOP').write_text('retained')
                with self.assertRaisesRegex(ValueError,'selection frozen'):archive.require_fresh_chain(root)
                self.assertTrue((root/name/'STOP').exists())
    def test_unrelated_cpu_work_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cpu').mkdir();archive.require_fresh_chain(root)
            self.assertTrue((root/'cpu').is_dir())
if __name__=='__main__':unittest.main()

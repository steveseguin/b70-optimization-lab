"""Real first-request analyzer on complete and damaged synthetic output."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import analyze
from test_analyze import sample


class FirstRequest(unittest.TestCase):
    def test_real_storage_floor(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import window
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(window.shutil,'disk_usage',return_value=SimpleNamespace(free=25_500_000_000+240_000_000)):
                self.assertEqual(window.storage(tmp,240_000_000)['root_stop_floor_bytes'],25_000_000_000)
            with patch.object(window.shutil,'disk_usage',return_value=SimpleNamespace(free=24_900_000_000+240_000_000)):
                with self.assertRaisesRegex(ValueError,'25 GB'):window.storage(tmp,240_000_000)

    def fixture(self, folder):
        rows=[dict(sample(arm=2,index=i),position=i) for i in range(3)]
        (folder/'result.json').write_text(json.dumps(dict(passed=True,
            arithmetic='iq3-p49-split32-v1',tokens=[9,9])))
        self.write(folder,rows)
        return rows

    def write(self,folder,rows):
        (folder/'measure.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def test_complete_and_each_empty_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);rows=self.fixture(folder)
            self.assertTrue(analyze.first_request(folder)['passed'])
            mutations={
                'miss_counts':lambda r:r.update(layers=[]),
                'miss_kernel':lambda r:r.update(events=[e for e in r['events'] if e['partition']!=2]),
                'resident_kernel':lambda r:r.update(events=[e for e in r['events'] if e['partition']!=1]),
                'overlap':lambda r:r.update(events=[e for e in r['events'] if e['projection']!=2]),
            }
            for name,mutate in mutations.items():
                with self.subTest(stream=name):
                    broken=copy.deepcopy(rows)
                    for row in broken:mutate(row)
                    self.write(folder,broken)
                    with self.assertRaises(ValueError):analyze.first_request(folder)
            self.write(folder,[])
            with self.assertRaises(ValueError):analyze.first_request(folder)
            (folder/'measure.jsonl').unlink()
            with self.assertRaises(FileNotFoundError):analyze.first_request(folder)


if __name__=='__main__':unittest.main()

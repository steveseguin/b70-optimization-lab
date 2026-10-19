"""Real saved device output through the actual unpatched report functions."""
import json, pathlib, subprocess, sys, unittest
P = pathlib.Path(__file__).resolve().parent
class RealReport(unittest.TestCase):
    def test_completed_smoke_real_report(self):
        code = '''import sys
sys.path.insert(0, sys.argv[1])
from report_recovery import report_completed
r = report_completed()
assert r['total_request_count'] == 24
assert r['postload_memory']['complete_postload']
assert all(len(v['requests']) == 12 and all(x['exact_oracle'] for x in v['requests']) for v in r['views'])
print('real report: 24 exact requests and complete postload observation')
'''
        p = subprocess.run([sys.executable,'-B','-c',code,str(P/'screen')],stdin=subprocess.DEVNULL,capture_output=True,text=True)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
if __name__ == '__main__': unittest.main()

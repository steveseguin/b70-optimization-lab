"""Remove only disposable CPU scratch after successful receipt sealing."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def main():
 receipt=json.loads((P/'build-receipt.json').read_text());assert receipt['passed']
 # Source paths are relative to repository root.
 protected={(P.parents[3]/x).resolve() for x in receipt['sources']}
 patterns=['integration-*','asan-v*','fixture-runs-*','fixture-first-v2','fixture-with-routes','first-mini','real-eight-*','failure-*','guard-tests','k2-manifest','k2-manifest-*','tmp']
 removed=[]
 for pattern in patterns:
  for d in B.glob(pattern):
   assert d.parent==B and not d.is_symlink()
   assert not any(q==d.resolve() or d.resolve() in q.parents for q in protected)
   removed.append(str(d.relative_to(P)))
   if d.is_dir():shutil.rmtree(d)
   else:d.unlink()
 (P/'scratch-cleanup.json').write_text(json.dumps(dict(passed=True,removed=sorted(removed),retained='Compiled binaries, build trees, generated sources and prepared window inputs; tracked gate receipts and verbatim fixture archive.'),indent=2)+'\n')
 print('removed',len(removed),'scratch paths')
if __name__=='__main__':main()

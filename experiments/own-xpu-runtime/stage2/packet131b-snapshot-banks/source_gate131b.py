"""Use the runtime repository-boundary check before writing any new CPU gate."""
from build131 import P, ROOT

def verify_sources(sources):
 from bootstrap import install
 # Importing bootstrap exposes the unchanged common verifier; no device work.
 from common import verify_map
 verify_map(ROOT, sources)
 # Oracle authority is validated separately, even when a target is in-repo.
 for name in sources:
  path = ROOT / name
  if path.is_relative_to(P / 'oracle'):
   raise ValueError('oracle authority must use static binding, not source map')
 return sources

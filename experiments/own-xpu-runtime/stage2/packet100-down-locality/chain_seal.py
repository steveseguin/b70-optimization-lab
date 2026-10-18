"""Hash-map verification for screen preparation; no record chain is registered."""
import hashlib
from pathlib import Path

def check_map(root,entries):
 if not isinstance(entries,dict) or not entries:raise ValueError('nonempty hash map required')
 for name,expected in entries.items():
  path=Path(root)/name;h=hashlib.sha256()
  with path.open('rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
  if h.hexdigest()!=expected:raise ValueError('source/artifact hash changed: '+str(path))

def main():raise ValueError('Packet100 has no qualified record chain; records require lane A and a qualified bundle')
if __name__=='__main__':main()

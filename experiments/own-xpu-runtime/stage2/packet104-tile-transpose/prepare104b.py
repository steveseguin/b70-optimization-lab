"""Restore small local input links, without copying or changing parent trees."""
import os
from build_engine import P,B,limits,sha

def main():
 limits();B.mkdir(exist_ok=True)
 links={B/'fusion-rope.hpp':P.parent/'packet100-down-locality/build/fusion-rope.hpp',
        B/'input':P.parent/'packet97-record-bundle/build/input',
        B/'fusion-fixtures':P.parent/'packet97-record-bundle/build/fusion-fixtures',
        P/'oracle':P.parent/'packet97-record-bundle/oracle'}
 for path,target in links.items():
  assert target.exists(),target
  if path.exists() or path.is_symlink():assert path.resolve()==target.resolve() or (path.is_file() and target.is_file() and sha(path)==sha(target)),path
  else:path.symlink_to(os.path.relpath(target,path.parent))
 print('local input links verified; parents untouched')
if __name__=='__main__':main()

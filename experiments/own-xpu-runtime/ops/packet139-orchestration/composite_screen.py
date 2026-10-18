"""Compatibility entry for the registered packet136 confirm/smoke commands."""
import sys
from source_decision import P
sys.path.insert(0,str(P))
from confirm136 import main
if __name__=='__main__':raise SystemExit(main())

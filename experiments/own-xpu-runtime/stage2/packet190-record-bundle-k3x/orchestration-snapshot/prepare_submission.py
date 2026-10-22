"""Final-location submission preparation; never posts. Real evidence rehearsal available."""
import sys
if '--rehearse-packet136' in sys.argv:
 from submission_rehearsal import main
else:
 from chain_adapter import install
 install()
 from submission_evidence import main
if __name__=='__main__':raise SystemExit(main())

"""Prepare only from a finished registered chain; never posts."""
from chain_adapter import install
install()
from submission_evidence import main
if __name__=='__main__':raise SystemExit(main())

"""Final submission CLI, with exact inherited receipt schema and packet124 pins."""
from chain_adapter import install
install()
import submission_cli
import submission_evidence
submission_cli.packet56_submission=submission_evidence
load_submitter=submission_cli.load_submitter
if __name__=='__main__':raise SystemExit(load_submitter().main())

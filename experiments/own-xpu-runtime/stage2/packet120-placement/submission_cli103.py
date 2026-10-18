"""Packet97e CLI; preparation/posting permissions remain the shared CLI's."""
import sys
import packet56_submission as submission103
sys.modules['packet56_submission']=submission103
from submission_cli import load_submitter
if __name__=='__main__':raise SystemExit(load_submitter().main())

"""Packet97e CLI; preparation/posting permissions remain the shared CLI's."""
import sys
import submission97e
sys.modules['packet56_submission']=submission97e
from submission_cli import load_submitter
if __name__=='__main__':raise SystemExit(load_submitter().main())

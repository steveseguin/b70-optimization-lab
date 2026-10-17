"""Packet79 entry: shared v4 lifecycle, copied placement policy, unchanged worker."""
import sys
from bootstrap import P,WRAPPER,install
install()
import screen

def worker_command(args,identity,manifest):
 return ['/usr/bin/python3','-B',str(P/'worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds',str(screen.WATCHDOG[args.profile])]

def main(argv=None):
 previous=screen.command;screen.command=worker_command
 try:return screen.main(argv)
 finally:screen.command=previous
if __name__=='__main__':raise SystemExit(main())

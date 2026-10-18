"""Coordinator-only entry; --plan performs CPU admission only."""
from screen_bridge import P,load
screen=load('packet68b_frozen_screen','screen.py')
command=screen.command
def local_command(*args):
 result=command(*args)
 assert result[2].endswith('/tp2_worker.py')
 result[2]=str(P/'screen_worker.py')
 return result
screen.command=local_command
if __name__=='__main__':raise SystemExit(screen.main())

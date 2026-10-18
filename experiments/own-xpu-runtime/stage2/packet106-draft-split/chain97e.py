"""Packet97e chain entry: preserve frozen screen sources/binaries, replace KD only."""
import sys
from pathlib import Path
P=Path(__file__).resolve().parent

def install():
    import queue_runner as q
    if not getattr(q.commands, '_packet97e', False):
        original=q.commands
        def commands(out):
            rows=original(out)
            for cmd in rows.values():
                i=cmd.index(str(P/'window.py'))
                cmd[i:i+1]=[str(P/'chain97e.py'),'window']
            return rows
        commands._packet97e=True
        q.commands=commands
    import window  # installs the production chain_pipeline alias first
    import kd_window97e
    sys.modules['draft_window']=kd_window97e
    return q,window

def main():
    role=sys.argv.pop(1)
    from startup_receipt97e import verify
    verify()
    q,w=install()
    if role=='queue':return q.main()
    if role=='window':return w.coordinated_main()
    raise ValueError('expected queue or window')
if __name__=='__main__':raise SystemExit(main())

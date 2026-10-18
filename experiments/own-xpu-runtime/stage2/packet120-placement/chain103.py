"""Packet97e chain entry: preserve frozen screen sources/binaries, replace KD only."""
import sys
from pathlib import Path
P=Path(__file__).resolve().parent

def install():
    import queue_runner as q
    if not getattr(q.commands, '_packet103e', False):
        original=q.commands
        def commands(out):
            rows=original(out)
            for cmd in rows.values():
                i=cmd.index(str(P/'window.py'))
                cmd[i:i+1]=[str(P/'chain103.py'),'window']
            return rows
        commands._packet103e=True
        q.commands=commands
    import window  # installs the production chain_pipeline alias first
    import kd_window103
    sys.modules['draft_window']=kd_window103
    return q,window

def main():
    from exec_limits import install as install_exec_limits
    install_exec_limits()
    role=sys.argv.pop(1)
    from startup_receipt103 import verify
    verify()
    q,w=install()
    if role=='queue':return q.main()
    if role=='window':return w.coordinated_main()
    raise ValueError('expected queue or window')
if __name__=='__main__':raise SystemExit(main())

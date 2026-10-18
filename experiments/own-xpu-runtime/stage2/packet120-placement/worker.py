"""Packet120 worker, copied v4 lifecycle with local split25 controller."""
from exec_limits import install as install_exec_limits
install_exec_limits()
from bootstrap import P, install
install()
import runpy
if __name__=='__main__':runpy.run_path(str(P/'runtime_worker.py'),run_name='__main__')

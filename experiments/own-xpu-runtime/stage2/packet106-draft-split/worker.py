"""Install packet91 placement, then execute the pinned shared v4 worker verbatim."""
import runpy
from bootstrap import WRAPPER,install
install()
if __name__=='__main__':runpy.run_path(str(WRAPPER/'tp2_worker.py'),run_name='__main__')

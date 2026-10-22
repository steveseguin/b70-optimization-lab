"""Install packet91 placement, then execute the pinned shared v4 worker verbatim."""
import runpy
from exec_limits import install as install_exec_limits
install_exec_limits()
from bootstrap import WRAPPER,install
install()
if __name__=='__main__':runpy.run_path(str(__import__('pathlib').Path(__file__).with_name('grid_worker.py')),run_name='__main__')

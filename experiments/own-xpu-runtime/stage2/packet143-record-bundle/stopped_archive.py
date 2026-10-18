"""A started packet91 chain freezes selection; never overwrite evidence."""
from pathlib import Path
def require_fresh_chain(build):
    for root in Path(build).glob('device-cards01-*'):
        raise ValueError('chain started; selection frozen: '+str(root))

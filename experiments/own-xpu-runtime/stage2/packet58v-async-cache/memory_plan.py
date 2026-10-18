"""58u measured admission plus a bounded allowance for the new async metadata."""
from legacy_memory_plan import *
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('p58v_measured',Path(__file__).parent/'host-admission/memory_plan.py')
_measured=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_measured)
EXTRA_HOST_BYTES=32*1024**2+1179648
PUBLICATION_DEVICE_BYTES=1179648

def window_plan(window,observation=None):
    budget=_measured.window_plan(window,view='tile16')
    if not window.startswith('K1'):
        budget['host_categories']['async_metadata_and_staging_bound']=EXTRA_HOST_BYTES
        budget['host_bound_bytes']+=EXTRA_HOST_BYTES
        budget['host_required_available_bytes']+=EXTRA_HOST_BYTES
        budget['async_device_staging_bytes']=PUBLICATION_DEVICE_BYTES
    return budget

def admit(snapshot,budget=None):
    import legacy_memory_plan
    budget=window_plan('WSCREEN') if budget is None else budget
    require(budget==window_plan(budget.get('window')), 'memory plan differs from sealed async policy')
    return legacy_memory_plan.admit(snapshot,budget)

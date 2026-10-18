"""Measured admission with full backing for extra immutable cache capacity."""
from legacy_memory_plan import *
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('p58af_measured',Path(__file__).parent/'host-admission/memory_plan.py')
_measured=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_measured)
ADMISSION=json.loads((Path(__file__).parent/'admission.json').read_text())['admission']
CACHE_BYTES=ADMISSION['cache_bytes']
PUBLICATION_DEVICE_BYTES=1179648
EXTRA_HOST_BYTES=32*1024**2+PUBLICATION_DEVICE_BYTES+ADMISSION['extra_cache_bytes']

def window_plan(window,observation=None):
    budget=_measured.window_plan(window,view='tile16')
    if not window.startswith('K1'):
        budget['device_categories']=dict(ADMISSION['device_categories'])
        budget['device_owned_bound_bytes']=ADMISSION['device_owned_bound_bytes']
        budget['driver_allowance_bytes']=ADMISSION['driver_allowance_bytes']
        budget['device_margin_bytes']=32_000_000_000-budget['device_owned_bound_bytes']-budget['driver_allowance_bytes']-1_500_000_000
        budget['host_categories']['capacity_backing_metadata_staging']=EXTRA_HOST_BYTES
        budget['host_categories']['new_observed_peak_increment']=ADMISSION['measured_host_peak_bytes']-budget['derivation']['measured_normalized_peak_bytes']
        budget['host_bound_bytes']=sum(budget['host_categories'].values())
        budget['host_required_available_bytes']=budget['host_bound_bytes']+HOST_RESERVE
        require(budget['host_required_available_bytes']==ADMISSION['host_required_available_bytes'],'admission derivation differs')
        budget['host_categories']['p58af_measurement_buffers']=4*1024**2
        budget['host_bound_bytes']+=4*1024**2
        budget['host_required_available_bytes']+=4*1024**2
        budget['async_device_staging_bytes']=PUBLICATION_DEVICE_BYTES
        budget['caveat']='One maximum allocation in every view; 18GB limits use, never admission. Live census, driver occupancy and host stops required.'
    return budget

def admit(snapshot,budget=None):
    import legacy_memory_plan
    budget=window_plan('WSCREEN') if budget is None else budget
    require(budget==window_plan(budget.get('window')), 'memory plan differs from sealed capacity policy')
    return legacy_memory_plan.admit(snapshot,budget)

def plan():
    return window_plan('WSCREEN')

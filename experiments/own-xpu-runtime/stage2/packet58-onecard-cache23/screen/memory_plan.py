"""Measured admission with full backing for extra immutable cache capacity."""
from legacy_memory_plan import *
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('p58ag_p58x_measured',Path(__file__).parent/'host-admission/memory_plan.py')
_measured=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_measured)
ADMISSION=json.loads((Path(__file__).parent/'admission.json').read_text())['admission']
CACHE_BYTES=ADMISSION['cache_bytes']
PUBLICATION_DEVICE_BYTES=1179648
EXTRA_HOST_BYTES=32*1024**2+PUBLICATION_DEVICE_BYTES+ADMISSION['extra_cache_bytes']+524288
USABLE_CACHE_BYTES=dict(ADMISSION['usable_cache_bytes'])

def window_plan(window,observation=None):
    budget=_measured.window_plan(window,view='tile16-resident')
    if not window.startswith('K1'):
        budget['device_categories']=dict(ADMISSION['device_categories'])
        budget['device_owned_bound_bytes']=ADMISSION['device_owned_bound_bytes']
        budget['driver_allowance_bytes']=ADMISSION['driver_allowance_bytes']
        # packet58-cache23: the bound is the exact physical remainder (floor - reserve - driver); the 240-byte
        # margin sits between the category sum and the bound (memory-plan.json).
        budget['physical_margin_bytes']=32_000_000_000-budget['device_owned_bound_bytes']-budget['driver_allowance_bytes']-1_500_000_000
        require(budget['physical_margin_bytes']>=0,'device bound exceeds the physical floor')
        budget['device_margin_bytes']=budget['device_owned_bound_bytes']-sum(budget['device_categories'].values())
        require(budget['device_margin_bytes']==ADMISSION['device_category_margin_bytes'],'device category margin differs from the admitted plan')
        require(budget['driver_allowance_bytes']>=ADMISSION['driver_overhead_measured_bytes'],'driver allowance below the measured lifetime overhead')
        budget['host_categories']['capacity_backing_metadata_staging']=EXTRA_HOST_BYTES
        budget['host_categories']['new_observed_peak_increment']=ADMISSION['measured_host_peak_bytes']-budget['derivation']['measured_normalized_peak_bytes']
        budget['host_bound_bytes']=sum(budget['host_categories'].values())
        budget['host_required_available_bytes']=budget['host_bound_bytes']+HOST_RESERVE
        require(budget['host_required_available_bytes']==ADMISSION['host_required_available_bytes'],'admission derivation differs')
        budget['async_device_staging_bytes']=PUBLICATION_DEVICE_BYTES
        budget['caveat']='One 23,049,601,024-byte allocation in every view; max (21,552,729,600) and max23 limit use, never admission. Live census, driver occupancy and host stops required.'
    return budget

def admit(snapshot,budget=None):
    import legacy_memory_plan
    budget=window_plan('WSCREEN') if budget is None else budget
    require(budget==window_plan(budget.get('window')), 'memory plan differs from sealed capacity policy')
    return legacy_memory_plan.admit(snapshot,budget)

def plan():
    return window_plan('WSCREEN')

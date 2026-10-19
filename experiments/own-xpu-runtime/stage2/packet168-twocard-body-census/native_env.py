"""Exact loader environment and record device visibility; passive only."""
from common import HERE,read,require
import chain_devices,launch_env
def environment(lane):
 env=launch_env.environment()
 if read(HERE/'identity.json')['gpu_count']==1:
  require(lane=='A','one-card lane A only')
  env.update(NEOReadDebugKeys='1',FilterBdfPath='0000:23:00.0',ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0')
 else:env=chain_devices.mask_native(env,lane)
 return env

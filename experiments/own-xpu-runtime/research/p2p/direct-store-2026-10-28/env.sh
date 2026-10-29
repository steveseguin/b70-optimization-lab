# Runtime environment for the 2026-10-28 direct-store lab (copied from /dev/shm/p2pbench/env.sh of 2026-10-25).
# ZE_AFFINITY_MASK=0,3 with PCI ordering exposes exactly 0000:23:00.0 and 0000:47:00.0; the binary also refuses any
# other visible GPU.
export PATH='/usr/bin:/bin'
export OMP_NUM_THREADS='2'
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
export HOME='/home/steve'
export ZE_ENABLE_PCI_ID_DEVICE_ORDER='1'
export ZE_AFFINITY_MASK='0,3'
export ONEAPI_DEVICE_SELECTOR='level_zero:*'

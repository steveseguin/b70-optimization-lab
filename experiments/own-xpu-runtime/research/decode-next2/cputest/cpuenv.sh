# Source: OpenCL CPU device only, GPU device nodes blocked by nodri.so.
export LD_PRELOAD=/dev/shm/ownrt-lab-dn2/cpu/nodri.so
export ONEAPI_DEVICE_SELECTOR=opencl:cpu
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/lib

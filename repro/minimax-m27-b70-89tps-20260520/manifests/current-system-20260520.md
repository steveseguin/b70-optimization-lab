# Current system manifest - 2026-05-20

## OS and kernel
Linux steve-TURIND8-2L2T 6.17.0-23-generic #23~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Tue Apr 14 16:11:48 UTC 2 x86_64 x86_64 x86_64 GNU/Linux
Distributor ID:	Ubuntu
Description:	Ubuntu 24.04.4 LTS
Release:	24.04
Codename:	noble

## Memory and disk
               total        used        free      shared  buff/cache   available
Mem:            15Gi       3.7Gi        10Gi       9.2Mi       1.3Gi        11Gi
Swap:           63Gi       2.4Gi        61Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1p2  457G  307G  127G  71% /
/dev/nvme0n1p1  916G  507G  363G  59% /mnt/fast-ai
/dev/nvme1n1p2  457G  307G  127G  71% /
NAME        TYPE   SIZE FSTYPE   MOUNTPOINTS                         MODEL
loop0       loop     4K squashfs /snap/bare/5                        
loop1       loop    74M squashfs /snap/core22/2292                   
loop2       loop    74M squashfs /snap/core22/2411                   
loop3       loop 252.8M squashfs /snap/firefox/8247                  
loop4       loop  18.5M squashfs /snap/firmware-updater/210          
loop5       loop  16.5M squashfs /snap/firmware-updater/226          
loop6       loop 531.4M squashfs /snap/gnome-42-2204/247             
loop7       loop 246.6M squashfs /snap/firefox/8274                  
loop8       loop  91.7M squashfs /snap/gtk-common-themes/1535        
loop9       loop 606.1M squashfs /snap/gnome-46-2404/153             
loop10      loop  66.8M squashfs /snap/core24/1587                   
loop11      loop   395M squashfs /snap/mesa-2404/1165                
loop12      loop  10.8M squashfs /snap/snap-store/1270               
loop13      loop  15.7M squashfs /snap/snap-store/1367               
loop14      loop   576K squashfs /snap/snapd-desktop-integration/343 
loop15      loop  49.3M squashfs /snap/snapd/26865                   
loop16      loop  48.1M squashfs /snap/snapd/25935                   
loop17      loop   580K squashfs /snap/snapd-desktop-integration/361 
loop18      loop 227.8M squashfs /snap/thunderbird/1104              
loop19      loop 227.8M squashfs /snap/thunderbird/1093              
loop20      loop  66.8M squashfs /snap/core24/1643                   
nvme0n1     disk 931.5G                                              Samsung SSD 9100 PRO 1TB
└─nvme0n1p1 part 931.5G ext4     /mnt/fast-ai                        
nvme1n1     disk 465.8G                                              Samsung SSD 960 EVO 500GB
├─nvme1n1p1 part     1G vfat     /boot/efi                           
└─nvme1n1p2 part 464.7G ext4     /                                   

## Intel GPU discovery
{
    "device_list": [
        {
            "device_function_type": "physical",
            "device_id": 0,
            "device_name": "Intel(R) Graphics [0xe223]",
            "device_type": "GPU",
            "drm_device": "/dev/dri/card3",
            "pci_bdf_address": "0000:03:00.0",
            "pci_device_id": "0xe223",
            "uuid": "00000000-0000-0003-0000-0000e2238086",
            "vendor_name": "Intel(R) Corporation"
        },
        {
            "device_function_type": "physical",
            "device_id": 1,
            "device_name": "Intel(R) Graphics [0xe223]",
            "device_type": "GPU",
            "drm_device": "/dev/dri/card4",
            "pci_bdf_address": "0000:83:00.0",
            "pci_device_id": "0xe223",
            "uuid": "00000000-0000-0083-0000-0000e2238086",
            "vendor_name": "Intel(R) Corporation"
        },
        {
            "device_function_type": "physical",
            "device_id": 2,
            "device_name": "Intel(R) Graphics [0xe223]",
            "device_type": "GPU",
            "drm_device": "/dev/dri/card2",
            "pci_bdf_address": "0000:a3:00.0",
            "pci_device_id": "0xe223",
            "uuid": "00000000-0000-00a3-0000-0000e2238086",
            "vendor_name": "Intel(R) Corporation"
        },
        {
            "device_function_type": "physical",
            "device_id": 3,
            "device_name": "Intel(R) Graphics [0xe223]",
            "device_type": "GPU",
            "drm_device": "/dev/dri/card0",
            "pci_bdf_address": "0000:e3:00.0",
            "pci_device_id": "0xe223",
            "uuid": "00000000-0000-00e3-0000-0000e2238086",
            "vendor_name": "Intel(R) Corporation"
        }
    ]
}

## XPU topology matrix
         GPU 0/0  GPU 1/0  GPU 2/0  GPU 3/0  CPU Affinity
GPU 0/0  S        NODE     NODE     NODE     0-15     
GPU 1/0  NODE     S        NODE     NODE     0-15     
GPU 2/0  NODE     NODE     S        NODE     0-15     
GPU 3/0  NODE     NODE     NODE     S        0-15     

## PCIe / driver snapshot
### 03:00.0
	NUMA node: 0
	Region 0: Memory at 285000000000 (64-bit, prefetchable) [size=16M]
	Region 2: Memory at 284800000000 (64-bit, prefetchable) [size=32G]
		LnkCap:	Port #0, Speed 2.5GT/s, Width x1, ASPM L0s L1, Exit Latency L0s <64ns, L1 <1us
		LnkSta:	Speed 2.5GT/s, Width x1
		LnkCap2: Supported Link Speeds: 2.5GT/s, Crosslink- Retimer- 2Retimers- DRS-
		LnkSta2: Current De-emphasis Level: -6dB, EqualizationComplete- EqualizationPhase1-
		Region 0: Memory at 0000285001000000 (64-bit, prefetchable)
		Region 2: Memory at 0000000000000000 (64-bit, prefetchable)
	Kernel driver in use: xe
	Kernel modules: xe
### 83:00.0
	NUMA node: 0
	Region 0: Memory at 207000000000 (64-bit, prefetchable) [size=16M]
	Region 2: Memory at 206800000000 (64-bit, prefetchable) [size=32G]
		LnkCap:	Port #0, Speed 2.5GT/s, Width x1, ASPM L0s L1, Exit Latency L0s <64ns, L1 <1us
		LnkSta:	Speed 2.5GT/s, Width x1
		LnkCap2: Supported Link Speeds: 2.5GT/s, Crosslink- Retimer- 2Retimers- DRS-
		LnkSta2: Current De-emphasis Level: -6dB, EqualizationComplete- EqualizationPhase1-
		Region 0: Memory at 0000207001000000 (64-bit, prefetchable)
		Region 2: Memory at 0000000000000000 (64-bit, prefetchable)
	Kernel driver in use: xe
	Kernel modules: xe
### a3:00.0
	NUMA node: 0
	Region 0: Memory at 189000000000 (64-bit, prefetchable) [size=16M]
	Region 2: Memory at 188800000000 (64-bit, prefetchable) [size=32G]
		LnkCap:	Port #0, Speed 2.5GT/s, Width x1, ASPM L0s L1, Exit Latency L0s <64ns, L1 <1us
		LnkSta:	Speed 2.5GT/s, Width x1
		LnkCap2: Supported Link Speeds: 2.5GT/s, Crosslink- Retimer- 2Retimers- DRS-
		LnkSta2: Current De-emphasis Level: -6dB, EqualizationComplete- EqualizationPhase1-
		Region 0: Memory at 0000189001000000 (64-bit, prefetchable)
		Region 2: Memory at 0000000000000000 (64-bit, prefetchable)
	Kernel driver in use: xe
	Kernel modules: xe
### e3:00.0
	NUMA node: 0
	Region 0: Memory at 8d000000000 (64-bit, prefetchable) [size=16M]
	Region 2: Memory at 8c800000000 (64-bit, prefetchable) [size=32G]
		LnkCap:	Port #0, Speed 2.5GT/s, Width x1, ASPM L0s L1, Exit Latency L0s <64ns, L1 <1us
		LnkSta:	Speed 2.5GT/s, Width x1
		LnkCap2: Supported Link Speeds: 2.5GT/s, Crosslink- Retimer- 2Retimers- DRS-
		LnkSta2: Current De-emphasis Level: -6dB, EqualizationComplete- EqualizationPhase1-
		Region 0: Memory at 000008d001000000 (64-bit, prefetchable)
		Region 2: Memory at 0000000000000000 (64-bit, prefetchable)
	Kernel driver in use: xe
	Kernel modules: xe

## Apt sources
/etc/apt/sources.list.d/oneAPI.list:1:deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main
/etc/apt/sources.list.d/kobuk-team-ubuntu-intel-graphics-noble.sources:2:URIs: https://ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/

## Key packages
intel-igc-core-2 2.32.7
intel-igc-opencl-2 2.32.7
intel-ocloc 26.14.37833.4-0
intel-oneapi-compiler-cpp-eclipse-cfg-2025.3 2025.3.3-30
intel-oneapi-compiler-cpp-eclipse-cfg-2026.0 2026.0.0-947
intel-oneapi-compiler-dpcpp-cpp 2026.0.0-947
intel-oneapi-compiler-dpcpp-cpp-2025.3 2025.3.2-832
intel-oneapi-compiler-dpcpp-cpp-2026.0 2026.0.0-947
intel-oneapi-compiler-dpcpp-cpp-common-2025.3 2025.3.3-30
intel-oneapi-compiler-dpcpp-cpp-common-2026.0 2026.0.0-947
intel-oneapi-compiler-dpcpp-cpp-runtime-2025.3 2025.3.3-30
intel-oneapi-compiler-dpcpp-cpp-runtime-2026.0 2026.0.0-947
intel-oneapi-compiler-dpcpp-eclipse-cfg-2025.3 2025.3.3-30
intel-oneapi-compiler-dpcpp-eclipse-cfg-2026.0 2026.0.0-947
intel-oneapi-compiler-shared-2025.3 2025.3.3-30
intel-oneapi-compiler-shared-2026.0 2026.0.0-947
intel-oneapi-compiler-shared-common-2025.3 2025.3.3-30
intel-oneapi-compiler-shared-common-2026.0 2026.0.0-947
intel-oneapi-compiler-shared-runtime-2025.3 2025.3.3-30
intel-oneapi-compiler-shared-runtime-2026.0 2026.0.0-947
intel-oneapi-dnnl-2026.0 2026.0.0-688
intel-oneapi-dnnl-devel-2026.0 2026.0.0-688
intel-oneapi-dpcpp-cpp-2025.3 2025.3.2-832
intel-oneapi-dpcpp-cpp-2026.0 2026.0.0-947
intel-oneapi-dpcpp-cpp-compiler 
intel-oneapi-mkl-classic-devel-2026.0 2026.0.0-908
intel-oneapi-mkl-classic-include-2026.0 2026.0.0-908
intel-oneapi-mkl-cluster-2026.0 2026.0.0-908
intel-oneapi-mkl-cluster-devel-2026.0 2026.0.0-908
intel-oneapi-mkl-core-2026.0 2026.0.0-908
intel-oneapi-mkl-core-devel-2026.0 2026.0.0-908
intel-oneapi-mkl-devel 2026.0.0-908
intel-oneapi-mkl-devel-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-blas-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-data-fitting-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-devel-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-dft-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-include-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-lapack-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-rng-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-sparse-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-stats-2026.0 2026.0.0-908
intel-oneapi-mkl-sycl-vm-2026.0 2026.0.0-908
intel-opencl-icd 26.14.37833.4-0
level-zero 1.28.2
level-zero-devel 1.28.2
libze-intel-gpu1 26.14.37833.4-0
libze1 1.28.2-local1
linux-image-6.17.0-14-generic 6.17.0-14.14~24.04.1
linux-image-6.17.0-22-generic 6.17.0-22.22~24.04.1
linux-image-6.17.0-23-generic 6.17.0-23.23~24.04.1
linux-image-generic-hwe-24.04 6.17.0-23.23~24.04.1
linux-image-unsigned-6.17.0-14-generic 
linux-image-unsigned-6.17.0-22-generic 
linux-image-unsigned-6.17.0-23-generic 
xpu-smi 1.3.6-1~24.04~ppa1

## Python stack
python 3.12.3 (main, Mar 23 2026, 19:04:32) [GCC 13.3.0]
platform Linux-6.17.0-23-generic-x86_64-with-glibc2.39
torch 2.11.0+xpu
torch_xpu_available True
torch_xpu_device_count 4
vllm 0.20.1

## oneAPI compiler
/opt/intel/oneapi/compiler/2025.3/bin/icpx
Intel(R) oneAPI DPC++/C++ Compiler 2025.3.2 (2025.3.2.20260112)
Target: x86_64-unknown-linux-gnu
Thread model: posix
InstalledDir: /opt/intel/oneapi/compiler/2025.3/bin/compiler
Configuration file: /opt/intel/oneapi/compiler/2025.3/bin/compiler/../icpx.cfg

## Source state
vllm:
c51df43005726a09c6eb7348e8c1b00501c70a8e
 benchmarks/kernels/benchmark_moe.py                |  122 ++-
 vllm/_custom_ops.py                                |   29 +
 vllm/_xpu_ops.py                                   |   44 +-
 vllm/benchmarks/latency.py                         |   21 +-
 vllm/benchmarks/throughput.py                      |   12 +-
 vllm/compilation/cuda_graph.py                     |   27 +
 .../passes/fusion/minimax_qk_norm_fusion.py        |  141 ++-
 .../passes/fusion/sequence_parallelism.py          |   26 +-
 vllm/compilation/passes/pass_manager.py            |   20 +-
 vllm/compilation/piecewise_backend.py              |   38 +-
 vllm/config/vllm.py                                |    7 +-
 vllm/distributed/device_communicators/all2all.py   |    5 +-
 .../base_device_communicator.py                    |   45 +-
 .../device_communicators/xpu_communicator.py       |   77 +-
 vllm/distributed/parallel_state.py                 |  120 ++-
 vllm/envs.py                                       |   12 +
 vllm/model_executor/kernels/linear/__init__.py     |    6 +
 .../model_executor/kernels/linear/scaled_mm/xpu.py |  181 ++++
 .../layers/fused_moe/router/base_router.py         |   14 +-
 .../layers/fused_moe/runner/moe_runner.py          |   68 +-
 vllm/model_executor/layers/layernorm.py            |   15 +-
 vllm/model_executor/layers/logits_processor.py     |  351 ++++++-
 .../model_executor/layers/mamba/gdn_linear_attn.py |   52 +-
 vllm/model_executor/layers/mamba/linear_attn.py    |  241 ++++-
 .../compressed_tensors/compressed_tensors.py       |   10 +-
 vllm/model_executor/layers/quantization/inc.py     |   15 +
 .../layers/quantization/moe_wna16.py               |  323 ++++++
 vllm/model_executor/models/minimax_m2.py           | 1063 +++++++++++++++++++-
 vllm/model_executor/models/qwen3_5.py              |   20 +-
 vllm/model_executor/models/qwen3_5_mtp.py          |   62 +-
 vllm/platforms/xpu.py                              |   21 +-
 vllm/v1/core/sched/scheduler.py                    |   36 +
 vllm/v1/executor/multiproc_executor.py             |   17 +
 vllm/v1/worker/gpu/model_runner.py                 |    6 +
 vllm/v1/worker/gpu_input_batch.py                  |   16 +-
 vllm/v1/worker/gpu_model_runner.py                 |  522 +++++++++-
 vllm/v1/worker/gpu_worker.py                       |   64 ++
 vllm/v1/worker/xpu_worker.py                       |   15 +
 38 files changed, 3653 insertions(+), 211 deletions(-)
llm-scaler:
4bfc0070090cc54afdb2d46b8e57882359141568
 .../csrc/moe_batch/moe_int4.sycl                   | 1380 +++++++++++++++++++-
 .../python/custom_esimd_kernels_vllm/__init__.py   |   37 +-
 .../python/custom_esimd_kernels_vllm/ops.py        |  168 ++-
 .../setup_moe_int4_only.py                         |   12 +-
 4 files changed, 1533 insertions(+), 64 deletions(-)

## Model files
113G	/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround
.gitattributes 1635
README.md 1363
added_tokens.json 1464
chat_template.jinja 6524
config.json 8542
configuration_minimax_m2.py 10158
generation_config.json 144
merges.txt 2414078
model-00001-of-00023.safetensors 5369526784
model-00002-of-00023.safetensors 5369526784
model-00003-of-00023.safetensors 5369526784
model-00004-of-00023.safetensors 5369530008
model-00005-of-00023.safetensors 5369533728
model-00006-of-00023.safetensors 5368718552
model-00007-of-00023.safetensors 5369533304
model-00008-of-00023.safetensors 5369533304
model-00009-of-00023.safetensors 5369533400
model-00010-of-00023.safetensors 5369533728
model-00011-of-00023.safetensors 5368718752
model-00012-of-00023.safetensors 5369533304
model-00013-of-00023.safetensors 5369533304
model-00014-of-00023.safetensors 5369533304
model-00015-of-00023.safetensors 5369533624
model-00016-of-00023.safetensors 5369533728
model-00017-of-00023.safetensors 5368718528
model-00018-of-00023.safetensors 5369533304
model-00019-of-00023.safetensors 5369533304
model-00020-of-00023.safetensors 5369533424
model-00021-of-00023.safetensors 5369533728
model-00022-of-00023.safetensors 5368718728
model-00023-of-00023.safetensors 2596866240
model.safetensors.index.json 14057148
modeling_minimax_m2.py 30914
quantization_config.json 6348
special_tokens_map.json 1504
tokenizer.json 15522763
tokenizer_config.json 11091
vocab.json 3905412
1094b395ca6a62487f4a58b518438a781d8f7a2d5978d50a6959cdc1fcccb914  /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround/config.json
969c2dd84d6514c5b59214824cbd29634326253c598ff701d531aefbe78ebb02  /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround/quantization_config.json
6ff90e975bec219135b35185377f3369c0497cea08d4b4f551743970c5e77ce7  /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround/model.safetensors.index.json
2fb1c28a83798e52fb41550d95cc6e93eb9db16fdc608c73c56172a72bb73581  /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround/tokenizer_config.json
e7b90ed7f55d905175bc26771d6d7d33b40b46742f073675bc816fedaf482ea1  /mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround/tokenizer.json

# Prepared binary SHA-256

All executables are under ignored `build/`. Native K0/G4 were compiled only, never run. Host fixture/model binaries ran CPU-only.

| Binary | SHA-256 |
| --- | --- |
| `p39-k0` | `82dc9d5afd72e669412d76c83b46e79e13f85f38dac6e1c4c2a73d78d5858ffe` |
| `p39-timing` | `82dc9d5afd72e669412d76c83b46e79e13f85f38dac6e1c4c2a73d78d5858ffe` |
| `cpu-gcc` | `c85777fdf4ad10bd391eec1e955557cfe3e1864566ad9fc16914092cea598e08` |
| `cpu-icpx` | `4b9652e6422e3c102e627c2979b4b8fcd4f9361731998abf913f171fdf016922` |
| `host-gate/own-rt-iq3-host` | `0a21f647c36f01fba8928e74470adafd6f08fbd732f30be70e93e37e3091656d` |

Rebuild procedures and source pins are in [INTEGRATE.md](INTEGRATE.md) and [build-receipt.json](build-receipt.json).

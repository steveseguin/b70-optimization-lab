# Prepared binary SHA-256

All executables are under ignored `build/`. Native K0/G4 were compiled only, never run. Host fixture/model binaries ran CPU-only.

| Binary | SHA-256 |
| --- | --- |
| `p39-k0` | `7a98d0ffcd59d009d8ce91414bd90bddfd9f8ea00cfaacfc3ee82514e7278153` |
| `p39-timing` | `7a98d0ffcd59d009d8ce91414bd90bddfd9f8ea00cfaacfc3ee82514e7278153` |
| `cpu-gcc` | `1a2a50a972aaef4e5c6b1cb013a779e9a7dd813b1bfec755852f981623e05df2` |
| `cpu-icpx` | `a803ca0f70f81df49b2fad26570bdda6dc4531520dfc8e5dac8abfc8f8060161` |
| `host-gate/own-rt-iq3-host` | `0a21f647c36f01fba8928e74470adafd6f08fbd732f30be70e93e37e3091656d` |

Rebuild procedures and source pins are in [INTEGRATE.md](INTEGRATE.md) and [build-receipt.json](build-receipt.json).

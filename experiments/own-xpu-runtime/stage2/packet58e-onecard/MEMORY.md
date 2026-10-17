# Packet58e memory admission

All arithmetic is recomputed from the pinned tensor and allocation censuses in
`memory_plan.py`. Decimal bytes are used below; the reserve is exactly 8 GiB.
The device arena ceiling, 1.5 GB card reserve, BF16 KV, blocks 54/56 offline
fence, anonymous-memory guard and original GPUActive shadow cap are unchanged.

| Initial exactness model admission | Bytes |
| --- | ---: |
| All 144 pinned expert banks | 48,627,712,000 |
| Full device bound as possible host backing | 26,409,219,600 |
| Observed shadow, retained 58c supervisor peak | 579,248,128 |
| Loader staging | 268,435,456 |
| Host workspace | 1,073,741,824 |
| Host cache metadata | 16,777,216 |
| Reserve | 8,589,934,592 |
| **Required MemAvailable** | **85,565,068,816** |

The full device charge contains 5,815,529,984 bytes of nonexpert weights,
18,000,000,000 cache bytes, 2,359,296 table bytes, 59,019,280 recurrent bytes,
116,391,936 BF16 KV/index bytes, two 1 GiB workspace/control allowances and
256 MiB transfer allowance. No future expert pin receives early accounting credit.

The seed comes from every saved 58c supervisor sample, recomputing
`max(0, GPUActive - admission_baseline - completed_census_pins)`.
Its raw inputs and hashes are under `evidence/58c-supervisor/`.
That failed run has **no successful after_load sample**. The 0.58 GB peak is
not a complete loaded-model measurement. All device backing stays reserved
independently, even after a later complete measurement is available.

The original admission additionally required all 33,323,087,360 bytes of clean
file-backed nonexpert/lookup pages to remain resident. Exactness does not
require that residency. The existing one-card loader uses sparse lookups and
does not pin or prefault all PLE/embedding pages. MemAvailable includes
reclaimable clean pages. They may reclaim through ordinary kernel operation;
there is no cache-drop, memory-setting or loader change. Paging can affect
speed, which is why shared-host windows carry no timing qualification.

Each successful full-model window requires the native after_load snapshot,
all 144 pinned banks with exact census sizes, the 18 GB cache, the full KV
census and live device allocations within the original bound. Their hashes
and all supervisor samples bind the next admission. The next observed shadow
is the maximum of the seed, the full-window supervisor peak and after_load
delta. No assumed zero shadow or teardown-only sample can qualify it.

GPUActive is host-global. Lane-B changes can inflate or mask its delta;
it is not a per-owner attribution claim. Keeping the complete device backing
bound independently prevents that ambiguity from removing allocation budgets.
The live supervisor still checks MemAvailable >= 8 GiB, the original shadow
cap, completed pin accounting, full anonymous RSS and the admitted combined
bound. Any failure saves the sample and requests SIGTERM once; no hard kill,
automatic retry or reserve reduction. Uncertain drain retains owner markers.

K1a/K1b use bounded fixtures and keep their original 12 GiB admission and
4 GiB shadow cap. WS128 keeps **118,308,908,048 bytes**, including full file-page
residency allowance, and whole-host lane admission. Admission is rechecked
after waiting for leases/drains. Swap never counts. This permits overlap when
memory is available; it does not guarantee every lane-B screen will fit.

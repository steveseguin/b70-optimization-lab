# Original card-3 G4 row-stride failure, 2026-10-12

Coordinator K0 at 03:53 UTC passed; G4 at 03:58 UTC completed five cases
(35 byte checks), then stopped at `hc-low-act` before launching that case.
The coordinator reported no fault and a clean kernel log. Original window,
stdout, kernel logs, raw arrays, failure and receipt are preserved byte-for-byte
under `g4-card3/`; K0 is under `k0-card3/`. `original-sha256.json` binds all
copied files, including the original source/build receipt. Originals in build/
were not edited. This repair ran CPU-only.

The validator wrongly used codes + FP32 scales and omitted expanded-layout
metadata. Q8 K10240 requires 10240 + 4*(10240/32) + 2*(10240/32) = 12160
bytes, while the check required 11520. Packed Q8 would be 10880; this was
neither packed/expanded confusion in the fixture nor a BF16 element-size or
split-four error. Q6 similarly retains 18 metadata bytes per 256 columns.
Variant 6 and variant 7 share the full expanded row layout; only reduction
splitting differs. The fixture was correct. The tiny CPU tests duplicated the
bad short formula and therefore did not expose it.

These are medians of 200 event-sum measurements per arm, in microseconds per
launch group (the entire chain). Per-token savings are the difference of those
medians times the pinned groups/token, converted to milliseconds. They are
screening arithmetic, not measured whole-token speedups. Every completed case
used eight rotated full-size buffers according to the archived executable's
source path; paired cases use two such buffers per bank. Control and candidate
used different banks per pair. No hardware cache-miss guarantee is claimed.

| Case | Unfused → fused µs/group | Groups/token | Saving ms/token | Bytes/weight buffer | Full-size rotation | Assembly |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `expert-act-iq2` | 74.0 → 69.9 | 47 | 0.1909 | 268,697,600 | Yes, eight banks | rejected |
| `expert-act-iq3` | 80.3 → 75.8 | 1 | 0.0045 | 360,448,000 | Yes, eight banks | rejected |
| `expert-checks-iq2` | 71.1 → 64.5 | 47 | 0.3133 | 268,697,600 | Yes, eight banks | admitted |
| `expert-checks-iq3` | 75.7 → 70.0 | 1 | 0.0057 | 360,448,000 | Yes, eight banks | rejected |
| `down-status` | 97.3 → 94.5 | 48 | 0.1350 | 471,859,200 | Yes, eight banks | admitted |

The activation rows already combine paired gate/up, both status checks and
activation; they are not activation-only. Both remain assembly-rejected for
added predicate spills. IQ3 checks-only remains rejected for an extra loop
instruction. Checks and full activation are mutually exclusive; never add
their savings. Seven other cases have no measurements in this window.
`completed-summary.json` derives these numbers from the retained arrays.

The repair retains the real layout check and shares the complete G4 fixture
and twelve-case registry with `g4_binding_gate.cpp`. CPU validation covers all
bank bindings, rejects the old truncated and packed strides, and tests
continuation after validation/mismatch failures. Native reruns need fresh
`k0-card3b` / `g4-card3b` outputs; old K0 cannot admit the rebuilt binary.

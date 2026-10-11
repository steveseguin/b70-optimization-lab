# CPU preparation closeout — round 6

Question: can packed IQ2_S/IQ3_S expert decode spend fewer instructions without
changing bytes, accumulation order or expert residency? Identity: packet9 SG32
control and the three variants in [README](README.md), installed icpx 2026.0.0,
offline BMG-G31; original normative grids, full precision arithmetic.

Outcome: native ISA produced and read; three kernels and two coordinator
programs compile. CPU bit/row/protocol tests pass in [build receipt](build-receipt.json).
No device program ran. No speed or full-model quality verdict is available.

Useful mechanism: packing two uint32 words reduces the emitted finite unpack
body; pair/pipeline retains the exact block order. Failure/uncertainty:
distributed IQ2 register lookup spills 6,016 bytes and requires all-bank
shuffles. UGM/SLM/shuffle latency and device issue utilization are assumptions.
AOT ISA is not the eventual runtime JIT. [Assembly receipt](assembly-receipt.json)
and [analysis](analysis.json) preserve counts, hashes and exact regeneration
commands; build/ISA scratch is deleted. Sources and negative variants remain.

Next: independently admitted card-3 exactness then paired full-block timing.
Revisit register lookup only with a smaller live-register working set or a
new demonstrated lookup scheme. Keep investigating packed decode; CPU
preparation does not finish the model lane or authorize a GPU launch.

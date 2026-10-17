# Packet53b CPU preparation closeout

Question: prepare an exact-order larger-V screen against the actual packet49c
controls, with no GPU use and a500 MB build cap. CPU preparation passed;
performance and device identity remain for the coordinator.

Identity: [manifest](manifest.json), [build receipt](build-receipt.json),
[control checks](control-identity.json), [CPU gates](cpu-gates.json),
[Python gates](python-gates.json), [register report](register-report.json),
[final seal](seal.json).

GNU and Intel each pass2,935,673 checks over2,750 sampled rows, with identical
output hash `4e4601f6ea577bb191930a887c09fd0a52082cee56eb2bd997d14ac604715dcb`. The15 full-shape M1 comparisons all match production and
the independent CPU reference. M2 mappings and distinct serial inputs are
covered in the small proof and are repeated at full shape by E1/E2.
ASan/UBSan passes the same count/hash. All17 mocked window/parser tests pass.
GNU/Intel/device builds pass; no device program was launched.

The initial paired V8/V16 kernels spill and are rejected. The retained
split-stream V8/V16 replacements report zero spills at128 GRFs. HC low keeps
the same64 bytes as its control. See [register details](REGISTER-REPORT.md)
and [negative index](DO-NOT-REPEAT.md) for rejected source and assembly.
A copied wrapper test initially expected the old1 GB error text; the actual
500 MB guard correctly refused. The final test checks the exact500 MB edge.

The largest recorded build size was196,154,028 bytes; final cleanup removed
67,576,213 bytes, leaving62,036,613 bytes. An earlier
logged cleanup also removed126,399,123 bytes of regenerable offline scratch.
All compiler refusals, CPU proof receipts and compressed native assembly stay.
No protected packet, chain, oracle unit or host setting was changed.

Next: coordinator [E1/E2 then T1/T2](WINDOW.md), with the same reviewed past
UTC boundary and exclusive device ownership after the record chain.
The common class choices must save≥35 µs in both owners. A pass feeds
[packet49d integration](INTEGRATION.md) in the next brief. No new CPU sweep
is warranted unless device evidence exposes a specific issue.

# Qwen3.8 repaired TP2/MTP0 D59r result

D59r fixed the startup-profile failure and completed all inference checks, but
formally failed its cross-TP exact-output gate.

- The 256-token bounded profile served successfully; no OOM or GPU fault.
- Full workload, cached-token, and objective canary gates passed.
- Class-balanced decode was 17.896698 tok/s; median TTFT was 195.835491 ms.
- Six of twelve full outputs exactly matched TP1 D54. Six differed, first at
  generated token indices 60, 181, 182, 437, 450, and 455.
- All objective quality canaries still passed and repeated greedy output had
  one class.

This is not a promoted TP2 result under D59r's preregistration. Cross-TP
floating-point reduction differences do not establish a quality regression,
so D60 freezes D59r as the TP2 comparator and requires an independent fresh TP2
run to reproduce every complete token stream before MTP is restored.

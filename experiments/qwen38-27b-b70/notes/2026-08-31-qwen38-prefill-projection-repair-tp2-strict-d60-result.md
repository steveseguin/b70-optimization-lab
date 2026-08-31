# Qwen3.8 repaired TP2/MTP0 D60 replay result

D60 established a deterministic repaired TP2 target baseline.

- All 12 complete token-ID streams exactly matched D59r.
- Cached tokens were zero, all objective canaries passed, and repeat-8 had one
  output class.
- Class-balanced decode was 18.067737 tok/s versus 17.896698 in D59r.
- Bounded startup, shutdown, and fault gates all passed.

Target-only eager TP2 is slower than qualified TP1 and is not a user speed
recommendation. Its value is as an exact TP2 comparator. D61 now adds MTP depth
1 and requires speculative verification to reproduce every D59r target token
while improving the strict class-balanced rate.

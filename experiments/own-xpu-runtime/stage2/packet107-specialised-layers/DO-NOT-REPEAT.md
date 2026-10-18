# Packet107 boundaries

- Shared GDN head preparation is closed: Intel NaN output payload changes from
  0x7fc1 to 0x7fc0. See `gdn-closeout.md`. No GDN device job is admitted.
- Do not duplicate a norm per consumer workgroup (packet94), serialize whole
  layers (packet24), or count fewer launches as performance (packets34/46).
- QSA local KV sharing is unmeasured. Keep all four heads' original reductions.
- No integration below 80 µs per layer in both fresh 128-token processes.
  A long-context-only improvement cannot satisfy that short-context threshold.
- Synthetic operator timings never become a model or LocalMaxxing headline.

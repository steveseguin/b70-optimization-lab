# Packet117 boundaries

- Do not reopen HC weight cache, norm-consumer fusion, four-stream geometry,
  virtual lane counts, or tile16 transposition. The only change is placement
  of independent sigmoid/product work before the same local barrier.
- Gate outputs are 10,240 BF16 values; 25,600 output bytes include the mix.
  Treating 6,400 values as the gate shape is incorrect.
- The useful-byte roofline includes software sigmoid and mixing. Do not call
  it measured DRAM bandwidth or infer that conversion dominates every cycle.
- Keep original 32-leaf trees, BF16 gate boundary, ordered four-term mix,
  full 16-bit KV, weights, target and all other runtime choices unchanged.
- No v5 run before <=0.70× in both orders/sites/layer types and both fresh
  micro processes, with exact bytes and clean drains. Stored booleans alone
  cannot satisfy the gate.
- GNU/Intel CPU agreement is not device equality. Synthetic micros and
  128-token one-load screens are not full realistic promotion evidence.

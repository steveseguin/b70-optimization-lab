# Packet112 boundaries

| Method | Decision / revisit condition |
| --- | --- |
| Reimplement route-fast as a new win | It is already selected by packet103 and timed by packet107/110. Compare against it. |
| Reconstruct router logits from packet100b IDs | Impossible; use the provenance-bound packet107 harness rows. |
| Rank logits or exponentials before normalized FP32 division | Excluded; rounding can create probability ties. |
| Interpret NaN/Inf rows as normal timing samples | Production rejects them. Check untouched outputs; exclude rejection time from speed gates. |
| Integrate before both fresh micro owners save >=50% | Forbidden. Keep the standalone micro and retain a failed gate as a closed arm. |
| CPU limit at module import | Forbidden; device jobs import these helpers. CPU CLI entrypoints only. |

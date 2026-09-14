# Receipt serialization attribution: small CPU win, no native promotion

September 14, 2026. After native screen02 completed and the application became
idle, replayed the frozen screen01 warm all48 boat's 528 call records. The
original writer uses sorted indented `json.dump`; the candidate uses sorted
compact `json.dumps` followed by one string write. Both retain exclusive file
creation, synchronous buffered writes and close; neither adds fsync. All fields
are preserved, with parsed equality checked after each arm. Preparation,
input parsing and verification are outside both arms' identical timer bounds.

Three alternating paired rounds saved 52.519, 55.256 and 52.436 milliseconds
across all 528 writes, median **52.519 ms**. Original writers took about 84–87 ms;
compact writers about 31.7–31.8 ms. A separately measured 528-call subset of
_context's two file reads, JSON parses and SHA hashes took a median **24.912 ms**.
That subset omits directory/fault checks; it is not a proposal to remove them.

This CPU/filesystem result cannot explain the roughly 1.2-second compiled
sampling penalty or establish an application speedup. It is too small to justify
an application reload on its own. Preserve the compact writer as a candidate
for a later combined, exactly validated build; keep current runtime unchanged.
Kernel overlap and synchronous filesystem work under native load are unmeasured.

[Results](../data/serializer-replay-cpu-01/result.json) and
[preregistration](../data/serializer-replay-cpu-01/preregistration.json) bind the
source and all original/output hashes. The full new local replay directory is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/serializer-replay-cpu-01`;
original evidence was unchanged. No Torch import, GPU request or setting change.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python scripts/run-multiblock-serializer-replay.py \
  --output-dir /mnt/fast-ai/bench-results/ltx25-baseline-20260913/serializer-replay-cpu-01 \
  --pairs 3
```

Next attribution target is repeated metadata and lifecycle traversal, measured
separately from native kernel work before proposing another runtime change.

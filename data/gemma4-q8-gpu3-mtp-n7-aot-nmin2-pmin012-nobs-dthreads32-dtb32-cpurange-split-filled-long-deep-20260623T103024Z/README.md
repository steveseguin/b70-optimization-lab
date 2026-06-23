# Failed Launch: CPU-Affinity Split

This run was intended to test target/draft CPU-affinity separation under the
current Gemma 4 Q8 filled-long draft-MTP record identity.

Result: no benchmark was run. The server exited before readiness because
llama.cpp `dec5ca557` rejects the draft batch CPU-range flag:

```text
error: invalid argument: --spec-draft-cpu-range-batch
```

The attempted extra args are preserved in `server.stdout.log` and the mirrored
server log under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/`.

Next attempt, if this lane is revisited: use only the supported draft CPU flags
(`--spec-draft-cpu-range` and `--spec-draft-cpu-strict`) and omit
`--spec-draft-cpu-range-batch`.

# W2m refused: the coordinator script omits a variable the model windows require (2026-10-12 23:17 UTC)

The first chains followed `coordinator_windows.sh` exactly: `env -i PATH=… LD_LIBRARY_PATH=…`.
At capacity 4,096 on cards 0+1 K0, K1a, K1b, K2, W0p and KD passed, and K0, K1a, K1b
passed at capacity 32,768 on cards 2+3. W2m then refused before launching anything:
`OMP_NUM_THREADS=2 required` (pipeline.py checks the coordinator's own environment for
single-prompt windows). Adding the variable for W2m alone would change the recorded
environment that every earlier receipt is bound to, so both chains are rerun with
`OMP_NUM_THREADS=2` in the environment of every window, under output directories
`build/c4096b` and `build/c32768b`. No device problem; no latch.

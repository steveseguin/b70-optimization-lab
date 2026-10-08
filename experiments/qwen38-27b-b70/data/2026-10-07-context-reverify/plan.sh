# Re-verification of the two public headline quoted-events runs on the patched harness (commit 59a201d3a).
# Same task bytes as the originals (copied from rd480q and rd1mq; expected.json hashes e8fd0d93… and d39a5522…).
SPARSE_ARGS="--density 3 --words" run rd480q-v2 ARMS="B32iq" KINDS=sparse SEEDS="0" SIZES=480000
SPARSE_ARGS="--density 3 --words" run rd1mq-v2 ARMS="B32iq" KINDS=sparse SEEDS="0" SIZES=1000000

#!/bin/bash
# packet 88: packet-86 instrumentation exactly (in-pipeline D2H fingerprints of
# packet 87 reverted after two freezes in two attempts). Warm + 120-prompt
# endurance on the sharded two-clip arm to reproduce the deterministic wrong
# clip with all inputs fingerprinted in receipts; root-cause then goes offline
# (replay the failing clip on the quiesced server).
#
# Expect: ~100 s warm, ~2.5-3 min endure generation, ~6 min verification.
#
#   bash scripts/run-campaign-88.sh
set -u
cd "$(dirname "$0")/.."
source ./scripts/lib-b70-campaign.sh
LANE=ltx25-baseline-20260913
require_no_fault
require_no_server
require_pm_on
require_journal_clean
step packet 88 prepared runtime ready
R=/mnt/fast-ai/bench-results/$LANE
P=$R/prepared-encoder-graph-capture-88
require_manifest $P
step campaign manifest verified
health_wait 1800
PID=$(python3 -c "import json;print(json.load(open('$R/encoder-server-graph-capture-88/server-identity.json'))['pid'])")
step server pid $PID up
arm f88-warm pipe-samp2-tsh 3 200988
arm f88-endure pipe-samp2-tsh 120 201088
step campaign complete

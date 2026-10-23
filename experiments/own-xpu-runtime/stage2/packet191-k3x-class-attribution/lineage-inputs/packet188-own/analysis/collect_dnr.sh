#!/bin/bash
# Collect every DO-NOT-REPEAT.md (stage2 packets + ops) into one searchable file (read-only).
cd /home/steve/llm-optimizations
OUT=$(dirname "$0")
find experiments/own-xpu-runtime -name DO-NOT-REPEAT.md -not -path '*/lineage*' -not -path '*/build/*' -not -path '*/orchestration-snapshot/*' | sort > $OUT/dnr-list.txt
: > $OUT/all-dnr.txt
while read f; do echo "=================== $f" >> $OUT/all-dnr.txt; cat "$f" >> $OUT/all-dnr.txt; done < $OUT/dnr-list.txt
wc -l $OUT/dnr-list.txt $OUT/all-dnr.txt

#!/bin/bash
# quiet-until-job.sh <lane> <job-name>: keep fn-run/QUIET until the job's terminal lane event (deadline 3 h), then remove it.
FN=/tmp/claude-1000/-home-steve/fn-run; L=/home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/lane-queue; dl=$(( $(date +%s) + 3*3600 ))
until grep "\"name\": \"$2\"" $L/events-$1.jsonl | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)'; do [ $(date +%s) -gt $dl ] && break; sleep 15; done
rm -f $FN/QUIET; echo "$(date -u +%T) quiet-until-job $2 ended; QUIET cleared" >> $FN/p58k.log

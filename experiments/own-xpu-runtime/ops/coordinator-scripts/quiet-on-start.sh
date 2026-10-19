#!/bin/bash
# quiet-on-start.sh <lane> <job-name>: when the job STARTs, write fn-run/QUIET; clear it at the job's terminal event (deadline 5 h).
FN=/tmp/claude-1000/-home-steve/fn-run; L=/home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/lane-queue; dl=$(( $(date +%s) + 5*3600 ))
until grep "\"name\": \"$2\"" $L/events-$1.jsonl 2>/dev/null | grep -q '"event": "START"'; do [ $(date +%s) -gt $dl ] && exit 3; sleep 10; done
echo "lane $1 timing $2 $(date -u +%FT%TZ)" > $FN/QUIET; echo "$(date -u +%T) quiet-on-start $2 started; QUIET set" >> $FN/p58k.log
until grep "\"name\": \"$2\"" $L/events-$1.jsonl | grep -qE '"event": "(DONE|FAILED|REFUSED|REFUSED-fast|REPORT-FAILED|REFUSED-PREDEVICE)'; do [ $(date +%s) -gt $dl ] && break; sleep 15; done
rm -f $FN/QUIET; echo "$(date -u +%T) quiet-on-start $2 ended; QUIET cleared" >> $FN/p58k.log

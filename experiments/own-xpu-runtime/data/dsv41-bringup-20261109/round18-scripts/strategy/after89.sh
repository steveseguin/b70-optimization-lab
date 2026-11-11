#!/bin/bash
# after tg89 ends: the plan-E exchange-overlap pre-check (six cards, ~2 min; its build is done)
W=/home/steve/dsv41-work
while systemctl --user is-active --quiet tg89; do sleep 5; done
echo "after89: tg89 ended $(date +%T)" >> $W/runs/after89.log
bash $W/xov/gate_xov_pull2q.sh
echo "after89: xov1 $(tail -1 $W/runs/xov1/summary.txt) $(date +%T)" >> $W/runs/after89.log

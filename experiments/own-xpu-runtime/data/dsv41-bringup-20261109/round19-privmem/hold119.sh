#!/bin/bash
# set locks/hold-tp119 once c118p has started (its lock check is at its start only), so chainq118p's later steps
# (tm1p ct1p lp1p ab2p) skip; chainq119 takes over after chainq118p ends
W=/home/steve/dsv41-work
until grep -qs "^c118p start" $(ls -td $W/runs/c118p-*/ 2>/dev/null | head -1)summary.txt; do sleep 5; done
echo "hold: tp119 build + kvshard gate after c118p ($(date '+%F %T'))" > $W/locks/hold-tp119
echo "$(date '+%F %T') hold-tp119 set (c118p running; tm1p..ab2p skip, chainq119 next)" >> $W/chainq118.txt

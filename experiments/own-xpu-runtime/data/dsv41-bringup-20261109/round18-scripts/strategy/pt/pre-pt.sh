#!/bin/bash
# before the iommu=pt reboot: wait for gate tg104c, then the peer benches with the IOMMU translating ("before")
W=/home/steve/dsv41-work
while systemctl --user is-active --quiet tg104c; do sleep 15; done
$W/pt/pt-bench.sh before
echo "pre-pt exit $? $(date +%T)" >> $W/runs/pt/bench-before.txt

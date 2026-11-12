#!/bin/bash
# run the overlap check (pb256/gate_xov2.sh) right after gate tg100 ends
W=/home/steve/dsv41-work
while systemctl --user is-active --quiet tg100; do sleep 10; done
until [ ! -e $W/six.active ]; do sleep 5; done
exec $W/pb256/gate_xov2.sh

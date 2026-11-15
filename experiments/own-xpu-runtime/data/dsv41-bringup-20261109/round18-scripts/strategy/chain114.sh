#!/bin/bash
# start tg114 after tg113c's unit ends (210 s quiet after its last engine), so the two gates do not interleave
while systemctl --user is-active -q tg113c; do sleep 30; done
sleep 210
exec /bin/bash /home/steve/dsv41-work/tg114.sh

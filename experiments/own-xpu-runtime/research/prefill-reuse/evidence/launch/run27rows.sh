#!/bin/bash
# run27.sh variant with a --rows argument: run27rows.sh LAUNCH OUT PROMPT ROWS
sed "s/--rows 32/--rows $4/" /dev/shm/ownrt-lab-prefill/launch/run27.sh > /dev/shm/ownrt-lab-prefill/launch/.run27-$4.sh
exec bash /dev/shm/ownrt-lab-prefill/launch/.run27-$4.sh "$1" "$2" "$3"

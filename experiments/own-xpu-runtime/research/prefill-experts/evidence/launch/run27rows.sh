#!/bin/bash
# run27rows.sh LAUNCH OUT PROMPT ROWS
sed "s/--rows 32/--rows $4/" /dev/shm/ownrt-lab-experts/launch/run27.sh > /dev/shm/ownrt-lab-experts/launch/.run27-$4-$$.sh
bash /dev/shm/ownrt-lab-experts/launch/.run27-$4-$$.sh "$1" "$2" "$3"; rc=$?; rm -f /dev/shm/ownrt-lab-experts/launch/.run27-$4-$$.sh; exit $rc

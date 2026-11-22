#!/bin/bash
# tp135 serve-1 + reset-1 engine tests in ONE engine start (phase reset): code identity, a follow-up turn vs a fresh
# read after a reset, p3k / analysis / x34k / x200k identity after resets, code again, EOS stop, stop request.
D=/home/steve/dsv41-serve/tests/out135; mkdir -p $D
/home/steve/dsv41-serve/preflight-serve.sh > $D/preflight.txt 2>&1 || { echo "preflight failed" >> $D/summary.txt; sync; exit 1; }
( while sleep 5; do sync; done ) & SY=$!
trap 'kill $SY 2>/dev/null; rm -f /home/steve/dsv41-work/six.active; sync' EXIT
B=/home/steve/dsv41-work/own_run_v41_tp135; M=$(python3 -I -c "import json;print(json.load(open('/home/steve/dsv41-serve/config.json'))['max_ctx'])")
/home/steve/dsv41-serve/venv/bin/python -I -u /home/steve/dsv41-serve/tests/t_engine.py $B $M reset $D x34k,x200k >> $D/summary.txt 2>&1
echo "t_engine exit $?" >> $D/summary.txt

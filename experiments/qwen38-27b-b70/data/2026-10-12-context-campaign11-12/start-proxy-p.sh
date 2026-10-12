#!/usr/bin/env bash
# The proxy for arm X32p (campaign 12, started by hand because the running campaign script starts a proxy only for
# the arms it knew at launch): campaign 12's options plus `recall` in item numbers. One state folder for all X32p
# runs (sessions are kept apart by the conversation's opening messages).
LAB=/home/steve/b70-optimization-lab
O=/mnt/fast-ai/bench-results/context-longrun-20261012
THINK_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)|^PROBE:|STREAM END|NOT RUN|Traceback|\(exit_code=[1-9-]'
RECITE_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)'
UNTIL_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
SCAN_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
LABEL_RE='(?m)^ITEM (\d+)/'
ss -tln | grep -q ":18200 " && { echo "port 18200 is in use"; exit 2; }
systemctl --user reset-failed ctx-keeper-proxy-p 2>/dev/null
systemd-run --user --unit=ctx-keeper-proxy-p --collect -p WorkingDirectory=$LAB python3 tools/ctxkeeper/ctxkeeper.py \
  --upstream "http://127.0.0.1:18196" --port 18200 --budget 32768 --reply-reserve 2048 --headroom 1024 --target-ratio 0.6 \
  --notes-thinking on --effort medium --think-when "$THINK_RE" --think-until "$UNTIL_RE" --recite-when "$RECITE_RE" \
  --notes-mode inplace --inplace-tokens 15000 --notes-checks near --max-recalls 16 --notes-scan "$SCAN_RE" \
  --recall-label "$LABEL_RE" --recall-unit item --state-dir "$O/proxy-state/p-shared" 2>&1 | tail -1
for i in $(seq 1 30); do curl -fsS -m 3 "http://127.0.0.1:18200/v1/models" >/dev/null 2>&1 && { echo "proxy up"; exit 0; }; sleep 1; done
echo "proxy did not come up"; exit 1

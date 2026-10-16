set -e
R=/mnt/fast-ai/bench-results/context-longrun-20261012
run() { # label msgs state_dir
  sd=$(for d in $3/*/; do n=$(python3 -I -c "import json;print(json.load(open('$d/state.json')).get('requests',0))"); echo "$n $d"; done | sort -rn | head -1 | cut -d' ' -f2)
  ratio=$(python3 -I -c "import json;print(json.load(open('$sd/state.json'))['ratio'])")
  cuts=$(python3 -I -c "import json;print(json.load(open('$sd/state.json'))['cuts'])")
  nch=$(python3 -I -c "
import json,statistics
v=[len(json.loads(l)['notes']) for l in open('$sd/notes-history.jsonl')]
print(int(statistics.mean(v)) if v else 0)")
  python3 -I comp.py $2 $1 $ratio $cuts $nch
}
for a in mini-swe-agent open-interpreter freeagent goose pi qwen-code; do run $a last-$a.json $R/c20b/proxy-state/AB-${a}__repair-n40-s2x; done
for a in cline openhands hermes-agent kimi-code forgecode; do run $a last-$a.json $R/c20d/proxy-state/AB-${a}__repair-n40-s2x; done
run mistral-vibe last-mistral-vibe.json $R/c20e/proxy-state/AB-mistral-vibe__repair-n40-s2x
run opencode last-opencode.json $R/c20f/proxy-state/AB-opencode__repair-n40-s2x
run G1-freeagent-c19 $R/client-repair2/runs/jobs/G1c__repair-n40-s2x/trial/agent/trajectory.json $R/c19c/proxy-state/G1
run FAp-freeagent-c15 $R/client-repair2/runs/jobs/FAp__repair-n40-s2x/trial/agent/trajectory.json $R/proxy-state/c15-FAp-repair-n40-s2x

#!/usr/bin/env bash
# Run every single-line `run:` command of .github/workflows/guides.yml on this
# machine (not the `pip install` setup lines), one result line per command.
# CPU only. Exit 1 if any command fails.
cd "$(dirname "$0")/.." || exit 2
fail=0
while IFS= read -r cmd; do
  out="$(nice -n 10 bash -c "$cmd" 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then echo "ok    $cmd"; else echo "FAIL  $cmd"; echo "$out" | tail -12 | sed 's/^/        /'; fail=1; fi
done < <(sed -n 's/^ *\(- \)\?run: \(.*\)$/\2/p' .github/workflows/guides.yml | grep -v -e '^|$' -e '^pip install')
exit $fail

#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a21-external-trace-client.sh"
expected_base=6f90e0b35496e61f808ed67b068ee84809bca39ab3644c333dfc5a46cf1a933a
expected_source=ceabc9ad4c0aedf1e22b71e1fd72566e22a344926c1ecfe490dda4d0ccfc7acf

derive() {
  Q38_A21_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a21/, "ple-only-a22")
  gsub(/attempt21/, "attempt22")
  gsub(/19693/, "19694")
  gsub(/supervise-tp4-mtp0-4352-ple-only-a22-trace\.sh/, "supervise-tp4-mtp0-4352-ple-only-a22-inner-trace.sh")
  gsub(/9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd/, "613afcc501331aa6ff7d5a238a6c9a5d45777b3e")
  gsub(/Q38_A21_VALIDATE_ONLY/, "Q38_A22_VALIDATE_ONLY")
  if ($0 == "expected_derived=552f707886836de9a5d74741a8eb081c4c140cfb767bda21eb7c8edecaa1962b")
    print "expected_derived=ae0f47a0e4972880d2b93ff91c25c5233360d7343482bcb53d61b964b9d520b1"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A22 inner-trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A22 client source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A22_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)

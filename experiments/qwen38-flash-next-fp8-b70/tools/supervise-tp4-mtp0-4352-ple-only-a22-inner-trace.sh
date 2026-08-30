#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a21-trace.sh"
expected_base=38426910becab553eac6149e5a412f6b568af417ceb75d327e03c9e841133773
expected_source=b51a3b05b9927460585040f66b03150387fa99c444e0854ddf77cd58f1c3473e

derive() {
  Q38_A21_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/launch-tp4-mtp0-4352-ple-only-a21-external-trace\.sh/, "launch-tp4-mtp0-4352-ple-only-a22-inner-trace.sh")
  gsub(/run-tp4-mtp0-4352-ple-only-a21-external-trace-client\.sh/, "run-tp4-mtp0-4352-ple-only-a22-inner-trace-client.sh")
  gsub(/ple-only-a21/, "ple-only-a22")
  gsub(/attempt21/, "attempt22")
  gsub(/19693/, "19694")
  gsub(/e60da9b46f31f43224d0564d519b801ee99ee133c042cacb4af1442da9bc18c5/, "18889ab0e8a8602bd02a22f775a903eafcc9ac4d2bd01db2ac0f102a9edc3c60")
  gsub(/6f90e0b35496e61f808ed67b068ee84809bca39ab3644c333dfc5a46cf1a933a/, "65c5dd11b4beb5d2d5796700cb071d25edcffe28dbe00c3b719ac3cb4602da84")
  gsub(/q38-ple4k-a15-rpc/, "q38-ple4k-a22-rpc")
  gsub(/9f720cd4aa6c8a8b045f54dfa10f5b8611caccbd/, "613afcc501331aa6ff7d5a238a6c9a5d45777b3e")
  gsub(/Q38_A21_VALIDATE_ONLY/, "Q38_A22_VALIDATE_ONLY")
  if ($0 == "expected_derived=b274d5a77d5323f3c5c2c854fa742c0010a4363312a4c01483b7a5bb0695b1f6")
    print "expected_derived=8494ab627ffa8b8e07f73120388ce779cafb89da0f65d487b220318d585df031"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A22 inner-trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A22 supervisor source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A22_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)

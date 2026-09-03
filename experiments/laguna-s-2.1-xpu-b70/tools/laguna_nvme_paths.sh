#!/usr/bin/env bash
# Fixed local-NVMe paths and fail-closed preflight for the additive Laguna lane.
# Source this file; do not execute it as a standalone launcher.
# The defaults are the originating host's layout. Override REPRO_MODEL_ROOT,
# REPRO_ARTIFACT_ROOT, REPRO_NVME_DEVICE, and REPRO_NVME_FSTYPE only when the
# same verified artifacts live elsewhere; every check below still fails closed.

readonly LAGUNA_NVME_DEVICE="${REPRO_NVME_DEVICE:-/dev/nvme0n1p2}"
readonly LAGUNA_NVME_FSTYPE="${REPRO_NVME_FSTYPE:-ext4}"
readonly LAGUNA_NVME_MODEL_ROOT="${REPRO_MODEL_ROOT:-/mnt/fast-ai/llm-models/laguna-s-2.1}"
readonly LAGUNA_NVME_TARGET_ROOT="$LAGUNA_NVME_MODEL_ROOT/int4"
readonly LAGUNA_NVME_DRAFT_ROOT="$LAGUNA_NVME_MODEL_ROOT/dflash-int4"
readonly LAGUNA_NVME_ARTIFACT_ROOT="${REPRO_ARTIFACT_ROOT:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1}"
readonly LAGUNA_NVME_BACKUP_ROOT=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1
readonly LAGUNA_NVME_CACHE_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT/cache"
readonly LAGUNA_NVME_TMP_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT/tmp"
readonly LAGUNA_NVME_RUN_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT/runs"
readonly LAGUNA_NVME_EVIDENCE_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT/evidence"
readonly LAGUNA_NVME_SOURCE_MANIFEST="$LAGUNA_NVME_MODEL_ROOT/.verification/source-files.sha256"
readonly LAGUNA_NVME_LOCAL_MANIFEST="$LAGUNA_NVME_MODEL_ROOT/.verification/nvme-files.sha256"
readonly LAGUNA_NVME_MANIFEST_SHA256=45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac

laguna_nvme_die() {
  echo "laguna NVMe preflight: $*" >&2
  return 1
}

laguna_nvme_canonical_existing() {
  local candidate="$1"
  realpath -e -- "$candidate" || laguna_nvme_die "cannot canonicalize required path: $candidate"
}

laguna_nvme_assert_not_backup_path() {
  local path="$1"
  case "$path" in
    /media|/media/*|"$LAGUNA_NVME_BACKUP_ROOT"|"$LAGUNA_NVME_BACKUP_ROOT"/*)
      laguna_nvme_die "active path resolves under external backup storage: $path"
      ;;
  esac
}

laguna_nvme_assert_nvme_mount() {
  local path="$1" source fstype
  read -r source fstype < <(findmnt --noheadings --output SOURCE,FSTYPE --target "$path") \
    || laguna_nvme_die "findmnt failed for $path"
  [[ "$source" == "$LAGUNA_NVME_DEVICE" && "$fstype" == "$LAGUNA_NVME_FSTYPE" ]] \
    || laguna_nvme_die "$path is mounted from $source ($fstype), expected $LAGUNA_NVME_DEVICE ($LAGUNA_NVME_FSTYPE)"
}

laguna_nvme_assert_fixed_path() {
  local expected="$1" actual
  actual="$(laguna_nvme_canonical_existing "$expected")" || return 1
  [[ "$actual" == "$expected" ]] \
    || laguna_nvme_die "required path is not canonical: $expected -> $actual"
  laguna_nvme_assert_not_backup_path "$actual"
  laguna_nvme_assert_nvme_mount "$actual"
}

laguna_nvme_verify_model_manifests() {
  local source_sha local_sha

  source_sha="$(sha256sum -- "$LAGUNA_NVME_SOURCE_MANIFEST")" || return 1
  source_sha="${source_sha%% *}"
  local_sha="$(sha256sum -- "$LAGUNA_NVME_LOCAL_MANIFEST")" || return 1
  local_sha="${local_sha%% *}"
  [[ "$source_sha" == "$LAGUNA_NVME_MANIFEST_SHA256" ]] \
    || laguna_nvme_die "retained source model manifest hash mismatch"
  [[ "$local_sha" == "$LAGUNA_NVME_MANIFEST_SHA256" ]] \
    || laguna_nvme_die "local model manifest hash mismatch"
  cmp -- "$LAGUNA_NVME_SOURCE_MANIFEST" "$LAGUNA_NVME_LOCAL_MANIFEST" \
    || laguna_nvme_die "retained source and local model manifests differ"
}

# This intentionally performs the expensive content verification only when a
# caller explicitly asks for it after the regular preflight has succeeded.
laguna_nvme_verify_model_contents() {
  (
    cd -- "$LAGUNA_NVME_MODEL_ROOT"
    sha256sum -c -- ".verification/nvme-files.sha256"
  )
}

laguna_nvme_prepare_paths() {
  local fixed_path

  [[ -d "$LAGUNA_NVME_MODEL_ROOT" ]] \
    || laguna_nvme_die "model root is absent: $LAGUNA_NVME_MODEL_ROOT (set REPRO_MODEL_ROOT to the verified Laguna model root)"
  [[ -d "$LAGUNA_NVME_ARTIFACT_ROOT" ]] \
    || laguna_nvme_die "artifact root is absent: $LAGUNA_NVME_ARTIFACT_ROOT (set REPRO_ARTIFACT_ROOT to a local NVMe artifact root)"
  for fixed_path in \
    "$LAGUNA_NVME_MODEL_ROOT" "$LAGUNA_NVME_TARGET_ROOT" "$LAGUNA_NVME_DRAFT_ROOT" \
    "$LAGUNA_NVME_ARTIFACT_ROOT"; do
    laguna_nvme_assert_fixed_path "$fixed_path"
  done
  laguna_nvme_verify_model_manifests

  mkdir -p -- "$LAGUNA_NVME_CACHE_ROOT/hf" "$LAGUNA_NVME_CACHE_ROOT/vllm" \
    "$LAGUNA_NVME_CACHE_ROOT/torchinductor" "$LAGUNA_NVME_CACHE_ROOT/triton" \
    "$LAGUNA_NVME_TMP_ROOT" "$LAGUNA_NVME_RUN_ROOT" "$LAGUNA_NVME_EVIDENCE_ROOT"
  for fixed_path in \
    "$LAGUNA_NVME_CACHE_ROOT" "$LAGUNA_NVME_TMP_ROOT" \
    "$LAGUNA_NVME_RUN_ROOT" "$LAGUNA_NVME_EVIDENCE_ROOT"; do
    laguna_nvme_assert_fixed_path "$fixed_path"
  done
}

laguna_nvme_prepare_run_dir() {
  local run_dir="$1" canonical
  [[ -n "$run_dir" ]] || laguna_nvme_die "run directory must not be empty"
  canonical="$(realpath -m -- "$run_dir")" || return 1
  [[ "$canonical" == "$run_dir" ]] \
    || laguna_nvme_die "run directory must already be canonical: $run_dir -> $canonical"
  case "$canonical" in
    "$LAGUNA_NVME_RUN_ROOT"/*) ;;
    *) laguna_nvme_die "run directory is outside the fixed NVMe run root: $canonical" ;;
  esac
  laguna_nvme_assert_not_backup_path "$canonical"
  mkdir -p -- "$canonical"
  laguna_nvme_assert_fixed_path "$canonical"
}

laguna_nvme_assert_fresh_run_path() {
  local run_dir="$1" canonical parent
  [[ -n "$run_dir" ]] || laguna_nvme_die "run directory must not be empty"
  canonical="$(realpath -m -- "$run_dir")" || return 1
  [[ "$canonical" == "$run_dir" ]] \
    || laguna_nvme_die "run directory must already be canonical: $run_dir -> $canonical"
  case "$canonical" in
    "$LAGUNA_NVME_RUN_ROOT"/*) ;;
    *) laguna_nvme_die "run directory is outside the fixed NVMe run root: $canonical" ;;
  esac
  laguna_nvme_assert_not_backup_path "$canonical"
  [[ ! -e "$canonical" ]] \
    || laguna_nvme_die "refusing to reuse existing run directory: $canonical"
  parent="$(dirname -- "$canonical")"
  laguna_nvme_assert_fixed_path "$parent"
}

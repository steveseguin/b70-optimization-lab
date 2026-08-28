#!/usr/bin/env bash
set -Eeuo pipefail

classifier=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/classify-q38-piecewise-graph-a5-kernel-journal.py
expected_classifier=440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16
tmp_dir=$(mktemp -d /tmp/q38-a5-journal-policy.XXXXXX)

cleanup() {
  find "$tmp_dir" -maxdepth 1 -type f -exec unlink -- {} \;
  rmdir -- "$tmp_dir"
}
trap cleanup EXIT

[[ $# == 0 ]] || { printf 'FAIL: policy fixture test takes no arguments\n' >&2; exit 2; }
printf '%s  %s\n' "$expected_classifier" "$classifier" | sha256sum -c - >/dev/null

cat >"${tmp_dir}/a4-actual.log" <<'EOF'
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 514
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]: It has been corrected by h/w and requires no further action
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]: event severity: corrected
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:  Error 0, type: corrected
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   section_type: PCIe error
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   port_type: 0, PCIe end point
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   version: 0.2
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   command: 0x0406, status: 0x0010
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   device_id: 0000:01:00.0
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   slot: 0
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   secondary_bus: 0x00
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   vendor_id: 0x144d, device_id: 0xa80a
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   class_code: 010802
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   bridge: secondary_status: 0x0000, control: 0x0000
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   aer_cor_status: 0x00000001, aer_cor_mask: 0x00000000
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   aer_uncor_status: 0x00000000, aer_uncor_mask: 0x00100000
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   aer_uncor_severity: 0x004f6030
Aug 28 11:20:28 steve-b70s kernel: {581}[Hardware Error]:   TLP Header: 00000000 00000000 00000000 00000000
Aug 28 11:20:28 steve-b70s kernel: nvme 0000:01:00.0: aer_status: 0x00000001, aer_mask: 0x00000000
Aug 28 11:20:28 steve-b70s kernel: nvme 0000:01:00.0:    [ 0] RxErr                  (First)
Aug 28 11:20:28 steve-b70s kernel: nvme 0000:01:00.0: aer_layer=Physical Layer, aer_agent=Receiver ID
EOF

"$classifier" "${tmp_dir}/a4-actual.log" "${tmp_dir}/a4-allowed.log"
tail -n +2 "${tmp_dir}/a4-allowed.log" | cmp -s - "${tmp_dir}/a4-actual.log"

cp "${tmp_dir}/a4-actual.log" "${tmp_dir}/mixed.log"
cat >>"${tmp_dir}/mixed.log" <<'EOF'
Aug 28 11:21:00 steve-b70s kernel: pcieport 0000:00:1f.0: AER: Corrected error message received from 0000:66:00.0
Aug 28 11:21:00 steve-b70s kernel: pcieport 0000:00:1f.0: PCIe Bus Error: severity=Corrected, type=Physical Layer
Aug 28 11:21:00 steve-b70s kernel: i210 0000:66:00.0: [ 0] RxErr (First)
EOF

cat >"${tmp_dir}/fatal.log" <<'EOF'
Aug 28 11:22:00 steve-b70s kernel: {900}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 514
Aug 28 11:22:00 steve-b70s kernel: {900}[Hardware Error]: event severity = fatal
Aug 28 11:22:00 steve-b70s kernel: {900}[Hardware Error]: device_id: 0000:01:00.0
Aug 28 11:22:00 steve-b70s kernel: nvme 0000:01:00.0: [ 0] RxErr (First)
EOF
printf '%s\n' 'Aug 28 11:23:00 steve-b70s kernel: xe 0000:47:00.0: reset started' >"${tmp_dir}/b70.log"
printf '%s\n' 'Aug 28 11:24:00 steve-b70s kernel: nvme nvme0: I/O timeout, reset controller' >"${tmp_dir}/timeout.log"

for fixture in mixed fatal b70 timeout; do
  if "$classifier" "${tmp_dir}/${fixture}.log" "${tmp_dir}/${fixture}.allowed.log" \
    >"${tmp_dir}/${fixture}.stdout" 2>"${tmp_dir}/${fixture}.stderr"; then
    printf 'FAIL: negative fixture unexpectedly passed: %s\n' "$fixture" >&2
    exit 1
  fi
done

printf 'PASS: actual attempt-4 block allowed; mixed, fatal, B70, and timeout fixtures refused\n'

#!/usr/bin/env python3
"""Generate the field-aware A48 twoshots packet from frozen A47 files."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD_HEAD = "797769b34b6db5c934609b75dc04cc61ec66e5f9"
NEW_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"
VERIFIER_SHA256 = "a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8"


def replace_exact(text: str, old: str, new: str, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"expected {count} copies of {old!r}, found {actual}")
    return text.replace(old, new)


def write_new(name: str, text: str) -> None:
    path = ROOT / name
    if os.environ.get("Q38_A48_REWRITE_VALIDATE_ONLY") == "1":
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"generated A48 source differs from {path}")
        return
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def launcher() -> None:
    source = ROOT / "launch-tp4-mtp0-2304-ple-only-a47-fullgraph.sh"
    text = source.read_text(encoding="utf-8")
    text = replace_exact(
        text, "/tmp/q38-ple2k-a47-base.sh", "/tmp/q38-ple2k-a48-base.sh"
    )
    text = replace_exact(
        text,
        "expected_derived=8831ce6a9515002f3b23244c590169286aeeb34b5fee83005ee617c31dde3a50",
        "expected_derived=a3bf49c3aad05f0245bc6ec1c0df19544860a7a2595d256a124af9a752bd108b",
    )
    text = replace_exact(text, "/tmp/q38-ple2k-a47-rpc", "/tmp/q38-ple2k-a48-rpc", 2)
    text = replace_exact(text, OLD_HEAD, NEW_HEAD, 2)
    text = replace_exact(text, "Q38_A47", "Q38_A48", 3)
    text = replace_exact(text, "A47", "A48", 5)
    text = replace_exact(text, "attempt47", "attempt48")
    text = replace_exact(text, "ATTEMPT=47 PORT=19719", "ATTEMPT=48 PORT=19720")
    text = replace_exact(
        text,
        '  print "export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096"\n'
        '  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"',
        '  print "export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096"\n'
        '  print "export CCL_SYCL_ALLREDUCE_LL=twoshots"\n'
        '  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"',
    )
    text = replace_exact(
        text,
        r'''  print "  printf '\''ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9\\n'\''"''',
        r'''  print "  printf '\''ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9\\n'\''"
  print "  printf '\''ccl_sycl_allreduce_ll=twoshots\\n'\''"''',
    )
    text = replace_exact(
        text,
        "grep -Fxq 'export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096' \"$derived\"",
        "grep -Fxq 'export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096' \"$derived\"\n"
        '[[ "$(grep -Fxc \'export CCL_SYCL_ALLREDUCE_LL=twoshots\' "$derived")" == 1 ]]\n'
        '[[ "$(grep -Fxc "  printf \'ccl_sycl_allreduce_ll=twoshots\\\\n\'" "$derived")" == 1 ]]',
    )
    text = replace_exact(
        text,
        'if [[ "${Q38_A48_VALIDATE_ONLY:-0}" != 1 ]]; then\n'
        "  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)",
        'if [[ "${Q38_A48_VALIDATE_ONLY:-0}" != 1 ]]; then\n'
        "  expected_nvme_aer_cor=${Q38_A48_NVME_AER_BASELINE:-}\n"
        "  expected_root_aer_cor=${Q38_A48_ROOT_AER_BASELINE:-}\n"
        '  [[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ ]] || {\n'
        "    printf 'FAIL: A48 requires numeric host-control AER baselines\\n' >&2\n"
        "    exit 1\n"
        "  }\n"
        "  mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)",
    )
    text = replace_exact(
        text,
        "  (( nvme_aer_cor == 0 && root_aer_cor == 0 )) || { printf 'FAIL: A48 requires zero current NVMe/root-port AER counters\\n' >&2; exit 1; }",
        "  (( nvme_aer_cor == expected_nvme_aer_cor && root_aer_cor == expected_root_aer_cor )) || { printf 'FAIL: A48 observed an AER increment after host-control baseline\\n' >&2; exit 1; }",
    )
    text = replace_exact(
        text,
        'if [[ "${Q38_A48_VALIDATE_ONLY:-0}" != 1 ]]; then\n'
        "  expected_nvme_aer_cor=${Q38_A48_NVME_AER_BASELINE:-}",
        'if [[ "${Q38_A48_VALIDATE_ONLY:-0}" != 1 ]]; then\n'
        '  [[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/usb-models)" == "/dev/sda2 fuseblk" ]] || {\n'
        "    printf 'FAIL: A48 evidence mount is not /dev/sda2 fuseblk\\n' >&2\n"
        "    exit 1\n"
        "  }\n"
        '  [[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/fast-ai)" == "/dev/nvme0n1p2 ext4" ]] || {\n'
        "    printf 'FAIL: A48 model mount is not /dev/nvme0n1p2 ext4\\n' >&2\n"
        "    exit 1\n"
        "  }\n"
        "  expected_nvme_aer_cor=${Q38_A48_NVME_AER_BASELINE:-}",
    )
    write_new("launch-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh", text)


def client() -> None:
    source = ROOT / "run-tp4-mtp0-2304-ple-only-a47-fullgraph-client.sh"
    text = source.read_text(encoding="utf-8")
    text = replace_exact(text, "a47", "a48", 5)
    text = replace_exact(
        text,
        "supervise-tp4-mtp0-2304-ple-only-a48-fullgraph.sh",
        "supervise-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh",
        2,
    )
    text = replace_exact(text, "A47", "A48")
    text = replace_exact(text, "attempt47", "attempt48", 3)
    text = replace_exact(text, "19719", "19720", 2)
    text = replace_exact(text, OLD_HEAD, NEW_HEAD, 3)
    text = replace_exact(
        text,
        "verify-q38-a46-fullgraph-runtime.py",
        "verify-q38-a48-fullgraph-runtime.py",
    )
    text = replace_exact(
        text,
        "expected_runtime_verifier=724528810e5316e1a32c013ecc6a2d0419f7063a7cedf6c5cb7d05d4ea672310",
        f"expected_runtime_verifier={VERIFIER_SHA256}",
    )
    text = replace_exact(
        text,
        "fi\ngrep -zFxq 'PYTHONPATH=",
        "fi\n"
        "grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' \"/proc/${server_pid}/environ\" || {\n"
        "  printf 'FAIL: live server lacks exact twoshots selector\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        "grep -zFxq 'PYTHONPATH=",
    )
    text = replace_exact(
        text,
        "  'libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700' 'ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9'; do",
        "  'libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700' 'ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9' \\\n"
        "  'ccl_sycl_allreduce_ll=twoshots'; do",
    )
    text = replace_exact(
        text,
        '        "ccl_kernel_sha256": "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9",',
        '        "ccl_kernel_sha256": "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9",\n'
        '        "ccl_sycl_allreduce_ll": "twoshots",',
    )
    text = replace_exact(
        text,
        '.ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and',
        '.ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and\n'
        '  .ccl_sycl_allreduce_ll == "twoshots" and',
    )
    write_new("run-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots-client.sh", text)


def supervisor() -> None:
    source = ROOT / "supervise-tp4-mtp0-2304-ple-only-a47-fullgraph.sh"
    text = source.read_text(encoding="utf-8")
    text = replace_exact(
        text,
        "launch-tp4-mtp0-2304-ple-only-a47-fullgraph.sh",
        "launch-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh",
    )
    text = replace_exact(
        text,
        "expected_wrapper=03769e4dba7b3f9e75d01ced227a5f035a3ab5260564ca841d1fe1b6581474c7",
        "expected_wrapper=7f4366a6358c3a3aed6a1326b68e700519cfc591fcfce2b0ffd3d922118b2eb1",
    )
    text = replace_exact(
        text,
        "run-tp4-mtp0-2304-ple-only-a47-fullgraph-client.sh",
        "run-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots-client.sh",
    )
    text = replace_exact(
        text,
        "expected_client=fcdcb8d2d1982ff8914a8a0803187502dd8b2736ac452a2d3670e72668a6947e",
        "expected_client=95a308a36a89414b661080df9945a621db7c9b6ba76e07b73a642d5d597e2a9a",
    )
    text = replace_exact(text, "a47", "a48", 2)
    text = replace_exact(text, "A47", "A48", 3)
    text = replace_exact(text, "attempt47", "attempt48", 4)
    text = replace_exact(text, "19719", "19720")
    text = replace_exact(text, OLD_HEAD, NEW_HEAD)
    text = replace_exact(
        text,
        'pressure_log="${evidence_dir}/host-pressure.tsv"\nchild=""',
        'pressure_log="${evidence_dir}/host-pressure.tsv"\n'
        "expected_nvme_aer_cor=${Q38_A48_NVME_AER_BASELINE:-}\n"
        "expected_root_aer_cor=${Q38_A48_ROOT_AER_BASELINE:-}\n"
        'child=""',
    )
    text = replace_exact(
        text,
        "  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \\\n"
        '    "$now" "$mem_available_kib" "$swap_total_kib" "$nvme_aer_cor" "$root_aer_cor" \\\n'
        '    "$mem_psi_some"',
        "  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \\\n"
        '    "$now" "$mem_available_kib" "$swap_total_kib" "$nvme_aer_cor" "$root_aer_cor" \\\n'
        '    "$expected_nvme_aer_cor" "$expected_root_aer_cor" \\\n'
        '    "$mem_psi_some"',
    )
    text = replace_exact(
        text,
        "  (( nvme_aer_cor == 0 && root_aer_cor == 0 )) || return 1",
        "  (( nvme_aer_cor == expected_nvme_aer_cor && root_aer_cor == expected_root_aer_cor )) || return 1",
        2,
    )
    text = replace_exact(
        text,
        "[[ $# == 0 ]] || { printf 'FAIL: supervisor takes no arguments\\n' >&2; exit 2; }",
        "[[ $# == 0 ]] || { printf 'FAIL: supervisor takes no arguments\\n' >&2; exit 2; }\n"
        '[[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ ]] || {\n'
        "  printf 'FAIL: A48 supervisor requires numeric host-control AER baselines\\n' >&2\n"
        "  exit 1\n"
        "}",
    )
    text = replace_exact(
        text,
        "printf 'timestamp\\tmem_available_kib\\tswap_total_kib\\tnvme_aer_corrected\\troot_aer_corrected\\tmemory_psi_some\\tmemory_psi_full\\tio_psi_some\\tio_psi_full\\tvmstat\\tnvme_diskstats\\taspm_policy\\n' >\"$pressure_log\"",
        "printf 'timestamp\\tmem_available_kib\\tswap_total_kib\\tnvme_aer_corrected\\troot_aer_corrected\\tnvme_aer_baseline\\troot_aer_baseline\\tmemory_psi_some\\tmemory_psi_full\\tio_psi_some\\tio_psi_full\\tvmstat\\tnvme_diskstats\\taspm_policy\\n' >\"$pressure_log\"\n"
        "printf 'nvme_aer_baseline=%s\\nroot_aer_baseline=%s\\n' \\\n"
        '  "$expected_nvme_aer_cor" "$expected_root_aer_cor" >"${evidence_dir}/aer-baseline.txt"',
    )
    text = replace_exact(
        text,
        '.ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and',
        '.ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and\n'
        '         .ccl_sycl_allreduce_ll == "twoshots" and',
    )
    text = replace_exact(
        text,
        '.identity.ccl_kernel_sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and',
        '.identity.ccl_kernel_sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and\n'
        '         .identity.ccl_sycl_allreduce_ll == "twoshots" and',
    )
    write_new("supervise-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh", text)


def host_wrapper() -> None:
    source = ROOT / "run-q38-a47-host-controlled.sh"
    text = source.read_text(encoding="utf-8")
    text = replace_exact(
        text,
        "supervise-tp4-mtp0-2304-ple-only-a47-fullgraph.sh",
        "supervise-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh",
    )
    text = replace_exact(
        text,
        "expected_supervisor=744c0dc1cda9370df71bd6ebbadd5242ec482871cbcaaae941cf194ccf57eb7a",
        "expected_supervisor=e0e8a407c8ccbdd2e05146fe76bd7791a37f533ca572a4007266e258e8a0db11",
    )
    text = replace_exact(text, "A47", "A48", 10)
    text = replace_exact(
        text,
        '[[ "$(sha256sum "$supervisor" | cut -d\' \' -f1)" == "$expected_supervisor" ]] || {\n'
        "  printf 'FAIL: A48 supervisor hash changed\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        "original_policy=",
        '[[ "$(sha256sum "$supervisor" | cut -d\' \' -f1)" == "$expected_supervisor" ]] || {\n'
        "  printf 'FAIL: A48 supervisor hash changed\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        '[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/usb-models)" == "/dev/sda2 fuseblk" ]] || {\n'
        "  printf 'FAIL: A48 evidence mount is not /dev/sda2 fuseblk\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        '[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/fast-ai)" == "/dev/nvme0n1p2 ext4" ]] || {\n'
        "  printf 'FAIL: A48 model mount is not /dev/nvme0n1p2 ext4\\n' >&2\n"
        "  exit 1\n"
        "}\n"
        "original_policy=",
    )
    text = replace_exact(
        text,
        "lspci -vv -s 01:00.0 | grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled'\n\n"
        'runuser -u steve -- "$supervisor" &',
        "lspci -vv -s 01:00.0 | grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled'\n"
        "export Q38_A48_NVME_AER_BASELINE\n"
        "export Q38_A48_ROOT_AER_BASELINE\n"
        "Q38_A48_NVME_AER_BASELINE=$(awk '$1 == \"TOTAL_ERR_COR\" {print $2}' \\\n"
        "  /sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable)\n"
        "Q38_A48_ROOT_AER_BASELINE=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n"
        '[[ "$Q38_A48_NVME_AER_BASELINE" =~ ^[0-9]+$ && "$Q38_A48_ROOT_AER_BASELINE" =~ ^[0-9]+$ ]] || {\n'
        "  printf 'FAIL: A48 could not establish numeric AER baselines\\n' >&2\n"
        "  exit 1\n"
        "}\n\n"
        'runuser -u steve -- "$supervisor" &',
    )
    text = replace_exact(
        text,
        "lspci -vv -s 00:03.1 | grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled'\n"
        "lspci -vv -s 01:00.0 | grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled'\n",
        "root_port_pci=$(lspci -vv -s 00:03.1)\n"
        "nvme_pci=$(lspci -vv -s 01:00.0)\n"
        "grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled' <<<\"$root_port_pci\"\n"
        "grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled' <<<\"$nvme_pci\"\n",
    )
    write_new("run-q38-a48-host-controlled.sh", text)


def main() -> None:
    launcher()
    client()
    supervisor()
    host_wrapper()


if __name__ == "__main__":
    main()

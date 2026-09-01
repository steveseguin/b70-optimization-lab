#!/usr/bin/env python3
"""Create A51 with an external-load-aware bounded local-NVMe guard."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A51_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh":
        "4ecbf76c233b520d7fd4e3e41ddd15ee7ac2ebd0d73d3ef2c8a008f4ac6c9fdf",
    "run-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots-client.sh":
        "8fbed5e5b7bd3fe101abaef631a962d9194021473ea54757b1afc7f0bab8f976",
    "supervise-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh":
        "b79008f44c2fd6c5d778029871e4ed8214f2b654a91cc14fd30324addce42ec7",
    "run-q38-a50-host-controlled.sh":
        "fe9cd341ce7d227a14f678d98017e7f3354bb68ab73732c1b22e7323dea1de46",
}


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    text = data.decode()
    assert not any("a50" in value or "a51" in value for value in re.findall(r"[0-9a-f]{64}", text))
    return text


def rep(text: str, old: str, new: str, count: int = 1) -> str:
    assert text.count(old) >= count, (old, text.count(old), count)
    return text.replace(old, new, count)


def successor(text: str) -> str:
    text = text.replace("attempt50", "attempt51")
    text = text.replace("19722", "19723")
    text = text.replace("ATTEMPT=50", "ATTEMPT=51")
    text = text.replace("a50", "a51")
    return text.replace("A50", "A51")


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = successor(source("launch-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh"))
    launcher = rep(
        launcher,
        "  expected_root_aer_cor=${Q38_A51_ROOT_AER_BASELINE:-}\n",
        "  expected_root_aer_cor=${Q38_A51_ROOT_AER_BASELINE:-}\n"
        "  expected_nvme_sectors_read=${Q38_A51_NVME_SECTORS_READ_BASELINE:-}\n",
    )
    launcher = rep(
        launcher,
        '  [[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ ]] || {\n',
        '  [[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ && \\\n'
        '     "$expected_nvme_sectors_read" =~ ^[0-9]+$ ]] || {\n',
    )
    launcher = rep(
        launcher,
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n",
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n"
        "  nvme_sectors_read=$(awk '$3 == \"nvme0n1\" {print $6}' /proc/diskstats)\n",
    )
    launcher = rep(
        launcher,
        "  (( nvme_aer_cor == expected_nvme_aer_cor && root_aer_cor == expected_root_aer_cor )) || { printf 'FAIL: A51 observed an AER increment after host-control baseline\\n' >&2; exit 1; }\n",
        "  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \\\n"
        "     nvme_aer_cor - expected_nvme_aer_cor <= 64 && \\\n"
        "     nvme_sectors_read >= expected_nvme_sectors_read && \\\n"
        "     nvme_sectors_read - expected_nvme_sectors_read <= 8388608 )) || {\n"
        "    printf 'FAIL: A51 bounded local-NVMe guard failed\\n' >&2; exit 1;\n"
        "  }\n",
    )
    launcher = rep(
        launcher,
        "expected_derived=a1cb7e42c17acbb787190925f1bb52b0335db7b9819c276a79980de71992354e",
        "expected_derived=" + "0" * 64,
    )
    env = os.environ.copy()
    env["Q38_A51_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots-client.sh"))
    client = client.replace("verify-q38-a51-fullgraph-runtime.py", "verify-q38-a48-fullgraph-runtime.py")

    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh"))
    supervisor = rep(
        supervisor,
        "expected_root_aer_cor=${Q38_A51_ROOT_AER_BASELINE:-}\n",
        "expected_root_aer_cor=${Q38_A51_ROOT_AER_BASELINE:-}\n"
        "expected_nvme_sectors_read=${Q38_A51_NVME_SECTORS_READ_BASELINE:-}\n"
        "max_nvme_aer_delta=64\nmax_nvme_sectors_read_delta=8388608\n",
    )
    supervisor = rep(
        supervisor,
        "  local now mem_available_kib swap_total_kib aspm_policy nvme_aer_cor root_aer_cor\n",
        "  local now mem_available_kib swap_total_kib aspm_policy nvme_aer_cor root_aer_cor nvme_sectors_read\n",
    )
    supervisor = rep(
        supervisor,
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n",
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n"
        "  nvme_sectors_read=$(awk '$3 == \"nvme0n1\" {print $6}' /proc/diskstats)\n",
    )
    supervisor = rep(
        supervisor,
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor) || return 1\n",
        "  root_aer_cor=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor) || return 1\n"
        "  nvme_sectors_read=$(awk '$3 == \"nvme0n1\" {print $6}' /proc/diskstats) || return 1\n",
    )
    supervisor = rep(
        supervisor,
        "  (( nvme_aer_cor == expected_nvme_aer_cor && root_aer_cor == expected_root_aer_cor )) || return 1\n",
        "  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \\\n"
        "     nvme_aer_cor - expected_nvme_aer_cor <= max_nvme_aer_delta && \\\n"
        "     nvme_sectors_read >= expected_nvme_sectors_read && \\\n"
        "     nvme_sectors_read - expected_nvme_sectors_read <= max_nvme_sectors_read_delta )) || return 1\n",
    )
    supervisor = rep(
        supervisor,
        "  ! grep -Eq 'nvme 0000:01:00\\.0:.*RxErr|device_id: 0000:01:00\\.0' \"${evidence_dir}/kernel-follow.log\" || return 1\n",
        "  ! grep -Eqi 'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down' \\\n"
        "    \"${evidence_dir}/kernel-follow.log\" || return 1\n",
    )
    supervisor = rep(
        supervisor,
        "  local device memory nvme_aer_cor root_aer_cor\n",
        "  local device memory nvme_aer_cor root_aer_cor nvme_sectors_read\n",
    )
    supervisor = rep(
        supervisor,
        "  ! grep -Eq 'nvme 0000:01:00\\.0:.*RxErr|device_id: 0000:01:00\\.0' \\\n"
        "    \"${evidence_dir}/kernel-journal.log\" || return 1\n",
        "  ! grep -Eqi 'event severity: (fatal|recoverable)|uncorrected|DPC:|link down|controller is down' \\\n"
        "    \"${evidence_dir}/kernel-journal.log\" || return 1\n",
    )
    supervisor = rep(
        supervisor,
        "  (( nvme_aer_cor == expected_nvme_aer_cor && root_aer_cor == expected_root_aer_cor )) || return 1\n",
        "  (( root_aer_cor == expected_root_aer_cor && nvme_aer_cor >= expected_nvme_aer_cor && \\\n"
        "     nvme_aer_cor - expected_nvme_aer_cor <= max_nvme_aer_delta && \\\n"
        "     nvme_sectors_read >= expected_nvme_sectors_read && \\\n"
        "     nvme_sectors_read - expected_nvme_sectors_read <= max_nvme_sectors_read_delta )) || return 1\n",
    )
    supervisor = rep(
        supervisor,
        '[[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ ]] || {\n',
        '[[ "$expected_nvme_aer_cor" =~ ^[0-9]+$ && "$expected_root_aer_cor" =~ ^[0-9]+$ && \\\n'
        '   "$expected_nvme_sectors_read" =~ ^[0-9]+$ ]] || {\n',
    )
    supervisor = rep(
        supervisor,
        "printf 'nvme_aer_baseline=%s\\nroot_aer_baseline=%s\\n' \\\n"
        '  "$expected_nvme_aer_cor" "$expected_root_aer_cor" >"${evidence_dir}/aer-baseline.txt"\n',
        "printf 'nvme_aer_baseline=%s\\nroot_aer_baseline=%s\\nnvme_sectors_read_baseline=%s\\n' \\\n"
        '  "$expected_nvme_aer_cor" "$expected_root_aer_cor" "$expected_nvme_sectors_read" >"${evidence_dir}/aer-baseline.txt"\n',
    )
    supervisor = rep(
        supervisor,
        '  Q38_A51_ROOT_AER_BASELINE="$expected_root_aer_cor" \\\n',
        '  Q38_A51_ROOT_AER_BASELINE="$expected_root_aer_cor" \\\n'
        '  Q38_A51_NVME_SECTORS_READ_BASELINE="$expected_nvme_sectors_read" \\\n',
    )
    supervisor = supervisor.replace(
        "expected_wrapper=4ecbf76c233b520d7fd4e3e41ddd15ee7ac2ebd0d73d3ef2c8a008f4ac6c9fdf",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=8fbed5e5b7bd3fe101abaef631a962d9194021473ea54757b1afc7f0bab8f976",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a50-host-controlled.sh"))
    host = rep(
        host,
        "export Q38_A51_ROOT_AER_BASELINE\n",
        "export Q38_A51_ROOT_AER_BASELINE\nexport Q38_A51_NVME_SECTORS_READ_BASELINE\n",
    )
    host = rep(
        host,
        "Q38_A51_ROOT_AER_BASELINE=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n",
        "Q38_A51_ROOT_AER_BASELINE=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)\n"
        "Q38_A51_NVME_SECTORS_READ_BASELINE=$(awk '$3 == \"nvme0n1\" {print $6}' /proc/diskstats)\n",
    )
    host = rep(
        host,
        '[[ "$Q38_A51_NVME_AER_BASELINE" =~ ^[0-9]+$ && "$Q38_A51_ROOT_AER_BASELINE" =~ ^[0-9]+$ ]] || {\n',
        '[[ "$Q38_A51_NVME_AER_BASELINE" =~ ^[0-9]+$ && "$Q38_A51_ROOT_AER_BASELINE" =~ ^[0-9]+$ && \\\n'
        '   "$Q38_A51_NVME_SECTORS_READ_BASELINE" =~ ^[0-9]+$ ]] || {\n',
    )
    host = host.replace(
        "expected_supervisor=b79008f44c2fd6c5d778029871e4ed8214f2b654a91cc14fd30324addce42ec7",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a51-host-controlled.sh", host)


if __name__ == "__main__":
    main()

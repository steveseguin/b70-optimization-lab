"""CPU-only, fail-closed admission helpers for every prepared device window."""
import os
from pathlib import Path

# Unknown environment names are refused, rather than trying to enumerate a
# version-dependent NEO debug registry. Ordinary shell/agent metadata is never
# forwarded to the native child; this also avoids writing credentials to receipts.
SHELL_KEYS = set("""INVOCATION_ID JOURNAL_STREAM SYSTEMD_EXEC_PID MEMORY_PRESSURE_WATCH MEMORY_PRESSURE_WRITE
AI_AGENT CLAUDECODE COLORTERM COREPACK_ENABLE_AUTO_PIN
DBUS_SESSION_BUS_ADDRESS DEBUGINFOD_URLS GH_PAGER GIT_EDITOR GIT_PAGER HOME LANG
LC_ALL LC_CTYPE LESSCLOSE LESSOPEN LOGNAME LS_COLORS NO_COLOR
NoDefaultCurrentDirectoryInExePath OLDPWD OMP_NUM_THREADS PAGER PATH PWD SHELL
SHLVL SSH_CLIENT SSH_CONNECTION SSH_TTY TERM USER XDG_DATA_DIRS XDG_RUNTIME_DIR
XDG_SESSION_CLASS XDG_SESSION_ID XDG_SESSION_TYPE _ TMPDIR LD_LIBRARY_PATH
OPENBLAS_NUM_THREADS MKL_NUM_THREADS PYTHONPATH PYTHONDONTWRITEBYTECODE
ONEAPI_DEVICE_SELECTOR SYCL_DEVICE_FILTER ZE_AFFINITY_MASK""".split())
NATIVE_KEYS = set("HOME LANG LC_ALL LC_CTYPE OMP_NUM_THREADS PATH TMPDIR LD_LIBRARY_PATH".split())

def environment_gate(env=None):
    env = dict(os.environ if env is None else env)
    unknown = sorted(k for k in env if k not in SHELL_KEYS and
                     not k.startswith(("CODEX_", "CLAUDE_")))
    # Present-but-empty keys are refused too. All other runtime/NEO options are
    # unknown and thus refused. An experiment must explicitly revise this policy.
    masked = [k for k in ("ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER", "ZE_AFFINITY_MASK") if env.get(k)]
    if unknown or masked:
        raise ValueError("unpreregistered environment keys refused before latch: " + ", ".join(unknown + masked))
    native = {k: v for k, v in env.items() if k in NATIVE_KEYS}
    return dict(native=native, relevant_environment={k: env[k] for k in sorted(env)
                if k in NATIVE_KEYS or k in ("ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER", "ZE_AFFINITY_MASK")},
                policy="closed environment; unknown names refused; native receives only recorded environment")

def memory_snapshot(path=Path("/proc/meminfo")):
    fields = {line.split(":")[0]: int(line.split()[1])*1024 for line in path.read_text().splitlines() if ":" in line}
    if "MemAvailable" not in fields:
        raise ValueError("MemAvailable missing")
    return dict(MemAvailable=fields["MemAvailable"], GPUActive=fields.get("GPUActive"),
                GPUActive_available="GPUActive" in fields)

def memory_admission(census, gemv, snapshot=None):
    sample = memory_snapshot() if snapshot is None else snapshot
    owned = census[gemv]["owned_peak_bytes_per_card"]
    table = 29321610240
    reserve = 0
    required = sum(owned)+table+reserve
    numbers = dict(**sample, owned_device_bytes=owned, host_backed_table_bytes=table,
                   reserve_bytes=reserve, required_MemAvailable=required)
    print("W2/W3 memory admission bytes: "+str(numbers), flush=True)
    if sample["MemAvailable"] < required:
        raise ValueError("MemAvailable below device shadows + host tables: "+str(numbers))
    return numbers

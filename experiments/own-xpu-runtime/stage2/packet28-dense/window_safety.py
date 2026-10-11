"""CPU-only admission policy; no device imports or discovery."""
import os
from pathlib import Path

SHELL_KEYS = set("""INVOCATION_ID JOURNAL_STREAM SYSTEMD_EXEC_PID MEMORY_PRESSURE_WATCH MEMORY_PRESSURE_WRITE
AI_AGENT CLAUDECODE COLORTERM COREPACK_ENABLE_AUTO_PIN DBUS_SESSION_BUS_ADDRESS DEBUGINFOD_URLS
GH_PAGER GIT_EDITOR GIT_PAGER HOME LANG LC_ALL LC_CTYPE LESSCLOSE LESSOPEN LOGNAME LS_COLORS
NO_COLOR NoDefaultCurrentDirectoryInExePath OLDPWD OMP_NUM_THREADS PAGER PATH PWD SHELL SHLVL
SSH_CLIENT SSH_CONNECTION SSH_TTY TERM USER XDG_DATA_DIRS XDG_RUNTIME_DIR XDG_SESSION_CLASS
XDG_SESSION_ID XDG_SESSION_TYPE _ TMPDIR LD_LIBRARY_PATH OPENBLAS_NUM_THREADS MKL_NUM_THREADS
PYTHONPATH PYTHONDONTWRITEBYTECODE ONEAPI_DEVICE_SELECTOR SYCL_DEVICE_FILTER ZE_AFFINITY_MASK""".split())
NATIVE_KEYS = set("HOME LANG LC_ALL LC_CTYPE OMP_NUM_THREADS PATH TMPDIR LD_LIBRARY_PATH".split())
MASKS = ("ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER", "ZE_AFFINITY_MASK")

def environment_gate(env=None):
    env = dict(os.environ if env is None else env)
    unknown = sorted(k for k in env if k not in SHELL_KEYS)
    masked = [k for k in MASKS if env.get(k)]
    if unknown or masked:
        raise ValueError("unpreregistered environment keys refused before latch: " + ", ".join(unknown + masked))
    if env.get("OMP_NUM_THREADS") != "2":
        raise ValueError("OMP_NUM_THREADS=2 required")
    native = {k: v for k, v in env.items() if k in NATIVE_KEYS}
    return dict(native=native, policy="closed environment; native receives only recorded allowlist")

def confined(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError("window writes must stay inside packet28")
    return path

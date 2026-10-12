"""CPU-only admission policy; no device imports or discovery."""
import os
from pathlib import Path

NATIVE_KEYS = set("HOME LANG OMP_NUM_THREADS PATH LD_LIBRARY_PATH".split())
WRAPPER_KEYS = {"XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"}

def native_key(key):
    return key in NATIVE_KEYS or key.startswith("LC_")

def environment_gate(env=None):
    env = dict(os.environ if env is None else env)
    unknown = sorted(k for k in env if not native_key(k) and k not in WRAPPER_KEYS)
    if unknown:
        raise ValueError("unpreregistered environment keys refused before latch: " + ", ".join(unknown))
    if env.get("OMP_NUM_THREADS") != "2":
        raise ValueError("OMP_NUM_THREADS=2 required")
    if not env.get("LD_LIBRARY_PATH"):
        raise ValueError("LD_LIBRARY_PATH is required from the coordinator")
    native = {k: v for k, v in env.items() if native_key(k)}
    return dict(native=native, policy="closed environment; native receives only recorded allowlist")

def confined(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root):
        raise ValueError("window writes must stay inside packet30")
    return path

#!/usr/bin/env python3
"""C66 exploratory full pi client, reusing C64's guarded task lifecycle.

Only run paths, the proxy launcher and additional source pins differ. The
unqualified C65 suffix affects shared main/notes headers; no recipe is promoted.
The imported C64 module is restored after this invocation for CPU test isolation.
"""
from contextlib import contextmanager
from pathlib import Path

import current_pi_probe as base

HERE = Path(__file__).resolve().parent
CONTROL = base.BASE / 'campaign66-current-pi-contract'
RUNS = base.BASE / 'runs/c66/pi'
STATE = base.BASE / 'proxy-state/c66-pi'
LAUNCHER = HERE / 'history_contract_keeper.py'
CONTRACT_SOURCE = HERE / 'main_history_contract_probe.py'
BASE_INPUT_PINS = base.input_pins
BASE_PROXY_COMMAND = base.proxy_command
_CONFIGURED = False


def input_pins():
    pins = BASE_INPUT_PINS()
    for path in (Path(__file__).resolve(), LAUNCHER, CONTRACT_SOURCE):
        pins['scripts'][str(path)] = base.sha(path)
    return pins


def proxy_command(upstream):
    argv = BASE_PROXY_COMMAND(upstream)
    production = str(base.LAB / 'tools/ctxkeeper/ctxkeeper.py')
    if argv.count(production) != 1:
        raise RuntimeError('base proxy command no longer has one production entrypoint')
    argv[argv.index(production)] = str(LAUNCHER)
    return argv


@contextmanager
def configured():
    global _CONFIGURED
    if _CONFIGURED:
        raise RuntimeError('nested C66 lifecycle configuration is not supported')
    changes = {'CONTROL': CONTROL, 'RUNS': RUNS, 'STATE': STATE,
               'TRIAL': RUNS / 'jobs' / base.JOB / 'trial',
               'input_pins': input_pins, 'proxy_command': proxy_command}
    original = {name: getattr(base, name) for name in changes}
    _CONFIGURED = True
    try:
        for name, value in changes.items():
            setattr(base, name, value)
        yield
    finally:
        for name, value in original.items():
            setattr(base, name, value)
        _CONFIGURED = False


def main():
    with configured():
        base.main()


if __name__ == '__main__':
    main()

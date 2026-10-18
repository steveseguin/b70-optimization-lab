#!/usr/bin/env python3
"""Render a future-packet patch from pinned Git bytes; never edit a packet."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def sources():
    pin = json.loads((HERE / 'chain-reference.json').read_text())
    result = {}
    for name, item in pin['sources'].items():
        data = subprocess.run(['git', 'show', pin['revision'] + ':' + item['path']],
                              cwd=HERE, capture_output=True, check=True, timeout=10).stdout
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('chain template source differs: ' + name)
        result[name] = data.decode()
    return result


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('chain patch anchor changed: ' + old[:80])
    return text.replace(old, new, 1)


def transform(name, text):
    if name == 'window_adapter.py':
        text = replace_once(text, '    def complete(self):\n', '''    def devices_drained(self):
        """Terminal owner boundary, after kernel postflight; no launches follow."""
        require(not self.record.get('devices_drained'), 'device phase already complete')
        try:
            self.monitor.finish()
            require(not self.window.startswith('W') or self.monitor.ready_checks > 0,
                    'model window lacks the before-request READY proof')
            self.record['clients_after_drain'] = admit_clients(self.scope, self.proc)
            self.drain.complete()
            # Publish completion under the shared flock, then release it before
            # CPU reporting. A later screen still observes the 60-second gap.
            self.drain.__exit__(None, None, None)
            self.lease.complete(drained=True)
            self.record['devices_drained'] = True
            self.record['released_before_report'] = True
        finally:
            self.persist()

    def complete(self):
''')
        old = '''            self.monitor.finish()
            require(not self.window.startswith('W') or self.monitor.ready_checks > 0,
                    'model window lacks the before-request READY proof')
            self.record['clients_after_drain'] = admit_clients(self.scope, self.proc)
            self.drain.complete()
            self.lease.complete(drained=True)
            self.record['passed'] = True'''
        text = replace_once(text, old, '''            if not self.record.get('devices_drained'):
                self.devices_drained()
            # Final receipt binding remains a separate quality/report gate.
            self.record['passed'] = True''')
    elif name == 'window.py':
        text = replace_once(text, '    def mark_launched(self,pid):\n', '''    device_phase_complete = False

    def finish_devices(self):
        if self.device_phase_complete:
            return
        require(not live_owner_pids(self), 'device owners still alive')
        self.postflight()
        if self.admission:
            self.admission.devices_drained()
        self.device_phase_complete = True

    def mark_launched(self,pid):
        require(not self.device_phase_complete, 'launch after terminal drain')
''')
        text = replace_once(text, '    def latch(self,reason):\n', '''    def latch(self,reason):
        if self.device_phase_complete:
            return  # CPU report/validator failure cannot poison device state.
''')
        text = replace_once(text, '    def check(self):\n        self.poll_kernel()', '''    def check(self):
        require(not self.device_phase_complete, 'device check after terminal drain')
        self.poll_kernel()''')
        text = replace_once(text, '''                wait_for_children()
                receipt=json.loads((dest/'receipt.json').read_text());require(receipt.get('passed') is True,'fixture native failure')''', '''                wait_for_children()
                if index + 1 == len(jobs):
                    watch.finish_devices()  # before the final CPU receipt validator
                receipt=json.loads((dest/'receipt.json').read_text());require(receipt.get('passed') is True,'fixture native failure')''')
        text = replace_once(text, '''        wait_for_children()
        for entry,child in zip(entries,children):''', '''        wait_for_children()
        # Last K fixture owner has exited. Run postflight and publish drain now,
        # before receipt hashing, K2 summaries or dispatch validators can raise.
        watch.finish_devices()
        for entry,child in zip(entries,children):''')
        text = replace_once(text, "        watch.postflight();record['passed']=True", "        watch.finish_devices();record['passed']=True")
    else:
        raise ValueError(name)
    return text


def render():
    return ''.join(''.join(difflib.unified_diff(text.splitlines(True),
        transform(name, text).splitlines(True), fromfile='a/' + name, tofile='b/' + name))
        for name, text in sources().items())


if __name__ == '__main__':
    (HERE / 'chain-window-drain.patch').write_text(render())

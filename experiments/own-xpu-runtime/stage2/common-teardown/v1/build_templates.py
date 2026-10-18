#!/usr/bin/env python3
"""Generate reviewable patches in this directory; never edit reference packets.

The transforms also let CPU tests execute patched source in temporary modules.
No packet is imported, sealed, registered or launched by this builder.
"""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE2 = HERE.parents[1]
REFERENCES = {'chain': STAGE2 / 'packet124b-record-bundle',
              'screen': STAGE2 / 'screen/v4-lanes'}


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('integration anchor absent or ambiguous: ' + old[:100])
    return source.replace(old, new, 1)


def chain_sources(root):
    source = (root / 'window_adapter.py').read_text()
    source = replace(source, 'import argparse\n',
                     'import argparse\nfrom teardown_on_error import StickyCheck, finish_chain_error\n')
    source = replace(source, '        self.scope = window_scope(window)\n',
                     '        self.scope = window_scope(window)\n'
                     '        self.watch = None\n'
                     '        self.failure_check = check = StickyCheck(check)\n')
    source = replace(source, '    def complete(self):\n', '    def complete_teardown(self):\n')
    source = replace(source, "            self.record['passed'] = True\n", '')
    source = replace(source, '            self.drain.complete()\n',
                     '            self.failure_check()\n            self.drain.complete()\n')
    source = replace(source, '    def __exit__(self, kind, value, trace):\n'
                     '        self.drain.__exit__(kind, value, trace)\n'
                     '        self.lease.__exit__(kind, value, trace)\n',
                     '    def complete(self):\n'
                     '        self.complete_teardown()\n'
                     "        self.record['passed'] = True\n"
                     '        self.persist()\n\n'
                     '    def __exit__(self, kind, value, trace):\n'
                     '        try:\n'
                     '            if value is not None:\n'
                     '                finish_chain_error(self, value)\n'
                     '        finally:\n'
                     '            self.drain.__exit__(kind, value, trace)\n'
                     '            self.lease.__exit__(kind, value, trace)\n')
    source = replace(source, "                bind_receipt(args.output / 'window.json', admission)\n"
                     '            return code\n',
                     "                bind_receipt(args.output / 'window.json', admission)\n"
                     '            else:\n'
                     "                finish_chain_error(admission, RuntimeError('window returned ' + str(code)))\n"
                     '            return code\n')
    window = (root / 'window.py').read_text()
    window = replace(window, "        text,self.cursor=journal();(out/'kernel-preflight.txt').write_text(text)\n",
                     "        text,self.cursor=journal();(out/'kernel-preflight.txt').write_text(text)\n"
                     '        if admission:admission.watch=self\n')
    window = replace(window, '    watch=Watch(out,boot,seconds,admission);old=',
                     '    failure=None\n    watch=Watch(out,boot,seconds,admission);old=')
    window = replace(window, "    except Exception as error:\n        record.update(error=str(error),passed=False)\n",
                     "    except Exception as error:\n        failure=error\n        record.update(error=str(error),passed=False)\n")
    window = replace(window, "    save(out/'window.json',record);return 0 if record['passed'] else 1\n",
                     "    save(out/'window.json',record)\n"
                     '    if failure is not None:raise failure\n'
                     "    return 0 if record['passed'] else 1\n")
    return {'window_adapter.py': source, 'window.py': window}


def screen_sources(root):
    source = (root / 'screen.py').read_text()
    source = replace(source, 'import argparse\n',
                     'import argparse\nfrom teardown_on_error import (VERSION, StickyCheck, drained_on_error,\n'
                     '                               finish_on_error, prove_screen_exit)\n')
    source = replace(source, 'def screen_main(argv=None, *, release=None):',
                     'def screen_main(argv=None, *, release=None, lifecycle=None):\n'
                     "    if lifecycle is None:lifecycle = {'launch_attempted': False}")
    source = replace(source, '    device_complete = False\n',
                     '    device_complete = False\n    postflight_complete = False\n')
    source = replace(source, '                child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)\n',
                     "                lifecycle['launch_attempted'] = True\n"
                     '                child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)\n')
    source = replace(source, '                                          drain_seconds=90, read_journal=S.journal))\n',
                     '                                          drain_seconds=90, read_journal=S.journal))\n'
                     "                postflight_complete = record.get('child_still_running') is False\n")
    source = replace(source, '    except Exception as error:\n        if device_complete:\n',
                     '    except Exception as error:\n'
                     '        if not device_complete and child is not None:\n'
                     '            def prove():\n'
                     "                require(postflight_complete, 'screen postflight incomplete')\n"
                     "                prove_screen_exit(record, child, read(args.output / 'run/teardown.json'), args.output)\n"
                     '            def complete():\n'
                     '                nonlocal device_complete\n'
                     '                coordination = release(record)\n'
                     '                device_complete = True\n'
                     '                record.update(device_complete=True, lease_released=True,\n'
                     '                              teardown_on_error=VERSION)\n'
                     "                atomic_json(args.output / 'lane-coordination.json', coordination)\n"
                     '            finish_on_error(error, prove=prove, complete=complete)\n'
                     '        if device_complete:\n')
    source = replace(source, "            save(args.output / 'report-failure.json', dict(passed=False, device_failure=False, error=str(error)))\n"
                     '            persist()\n            return 1\n',
                     "            save(args.output / 'report-failure.json', dict(passed=False, device_failure=False, error=str(error)))\n"
                     '            persist()\n            raise\n')
    source = replace(source, "    lease = Reservation(args.lane, window='screen', check=check)\n",
                     '    check = StickyCheck(check)\n'
                     "    lifecycle = {'launch_attempted': False}\n"
                     "    lease = Reservation(args.lane, window='screen', check=check)\n")
    source = replace(source, '            return screen_main(argv, release=release)\n',
                     '            def prove_unstarted():\n'
                     '                if lease.completed:\n'
                     '                    return\n'
                     "                require(not lifecycle['launch_attempted'], 'screen launch may have occurred')\n"
                     '                check()\n'
                     '            def release_unstarted():\n'
                     '                if not lease.completed:\n'
                     '                    lease.complete(drained=True)\n'
                     '            with drained_on_error(prove=prove_unstarted, complete=release_unstarted):\n'
                     '                code = screen_main(argv, release=release, lifecycle=lifecycle)\n'
                     "                if code and not lifecycle['launch_attempted']:\n"
                     "                    finish_on_error(RuntimeError('screen refused before launch'),\n"
                     '                                    prove=prove_unstarted, complete=release_unstarted)\n'
                     '                return code\n')
    conditions = (root / 'conditions.py').read_text()
    conditions = replace(conditions, 'import fcntl\n',
                         'import fcntl\nfrom teardown_on_error import finish_on_error\n')
    conditions = replace(conditions, '                 on_refusal=None):\n',
                         '                 on_refusal=None, prove_drained=None):\n')
    conditions = replace(conditions, '        self.on_refusal = on_refusal\n',
                         '        self.on_refusal = on_refusal\n        self.prove_drained = prove_drained\n')
    conditions = replace(conditions,
        '    def __exit__(self, kind, value, trace):\n'
        '        try:\n'
        '            if kind is None:\n'
        '                self.record.update(drained=True, completed_monotonic=self.now())\n'
        "                save(self.root / 'teardown-state.json', self.record)\n"
        "                save(self.output / 'teardown.json', self.record)\n"
        '        finally:\n'
        '            self.lock.close()\n',
        '    def complete(self):\n'
        '        if self.prove_drained is not None:\n'
        '            self.prove_drained()\n'
        '        self.record.update(drained=True, completed_monotonic=self.now())\n'
        "        save(self.root / 'teardown-state.json', self.record)\n"
        "        save(self.output / 'teardown.json', self.record)\n\n"
        '    def __exit__(self, kind, value, trace):\n'
        '        try:\n'
        '            if kind is None:\n'
        '                self.complete()\n'
        '            elif self.prove_drained is not None:\n'
        '                finish_on_error(value, prove=self.prove_drained, complete=self.complete)\n'
        '        finally:\n'
        '            self.lock.close()\n')
    worker = (root / 'tp2_worker.py').read_text()
    worker = replace(worker, 'import argparse\n',
                     'import argparse\nfrom teardown_on_error import StickyCheck, prove_transport_exit\n'
                     'from common import S, require\nimport fault_review\n')
    worker = replace(worker, 'from conditions import LANES, Teardown, lane_gate\n',
                     'from conditions import LANES, Teardown, lane_gate, selected_clients\n')
    worker = replace(worker, '    with Teardown(output, on_refusal=refused):\n',
                     '    def prove_drained():\n'
                     '        prove_transport_exit(transport)\n'
                     '        selected_clients(transport.teardown_lane)\n'
                     '    with Teardown(output, on_refusal=refused, prove_drained=prove_drained):\n')
    worker = replace(worker, '    transport = pipeline.Transport.__new__(pipeline.Transport)\n',
                     '    # Use the parent-approved boundary, including worker startup; never advance it.\n'
                     "    teardown_cursor = read(output.parent / 'window.json')['coordinator_fault_review']['cursor']\n"
                     "    require(isinstance(teardown_cursor, str) and teardown_cursor, 'missing fault boundary')\n"
                     '    def teardown_check():\n'
                     '        fresh, _ = S.journal(teardown_cursor)\n'
                     "        require(not fault_review.fault_lines(fresh), 'new GPU fault before drain completion')\n"
                     '    transport = pipeline.Transport.__new__(pipeline.Transport)\n'
                     '    transport.teardown_check = StickyCheck(teardown_check)\n'
                     "    transport.teardown_lane = identity['lane']\n")
    return {'screen.py': source, 'conditions.py': conditions, 'tp2_worker.py': worker}


def main():
    manifest = {'schema': 'own-runtime.teardown-on-error.templates.v1', 'integrations': {}}
    for kind, render in (('chain', chain_sources), ('screen', screen_sources)):
        root = REFERENCES[kind]
        rows, patches = {}, []
        for name, changed in render(root).items():
            original = (root / name).read_bytes()
            compile(changed, name, 'exec')
            rows[name] = dict(before_sha256=hashlib.sha256(original).hexdigest(),
                              after_sha256=hashlib.sha256(changed.encode()).hexdigest())
            patches.extend(difflib.unified_diff(original.decode().splitlines(True), changed.splitlines(True),
                                               fromfile='a/' + name, tofile='b/' + name))
        patch_name = kind + '-integration.patch'
        # Git accepts an empty context line without its optional leading space;
        # avoid storing trailing whitespace in the patch artifact itself.
        (HERE / patch_name).write_text(''.join('\n' if line == ' \n' else line for line in patches))
        manifest['integrations'][kind] = dict(reference=str(root.relative_to(STAGE2)),
                                             patch=patch_name, files=rows)
    manifest['helper_sha256'] = hashlib.sha256((HERE / 'teardown_on_error.py').read_bytes()).hexdigest()
    (HERE / 'templates.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

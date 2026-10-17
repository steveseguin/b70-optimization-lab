"""CPU-only write admission, shared by preflight and the KD writer."""
from pathlib import Path
import os
import stat


def inside(path, boundary, *, tree=False):
    path, boundary = Path(path).absolute(), Path(boundary).resolve()
    resolved = path.resolve()
    if resolved != boundary and boundary not in resolved.parents:
        raise ValueError('write/scratch outside packet boundary: ' + str(path))
    # Resolving first alone loses evidence of a symlink within an admitted tree.
    for part in (path, *path.parents):
        if part == boundary:
            break
        if part.is_symlink():
            raise ValueError('write/scratch symlink: ' + str(part))
    if tree and path.exists():
        inodes = {}
        for entry in [path, *path.rglob('*')]:
            st = entry.lstat()
            if stat.S_ISLNK(st.st_mode):
                raise ValueError('write/scratch symlink: ' + str(entry))
            if stat.S_ISREG(st.st_mode):
                key = (st.st_dev, st.st_ino)
                count, links = inodes.get(key, (0, st.st_nlink))
                inodes[key] = (count + 1, links)
            elif not stat.S_ISDIR(st.st_mode):
                raise ValueError('non-regular scratch member: ' + str(entry))
        if any(count != links for count, links in inodes.values()):
            raise ValueError('write/scratch hardlink outside admitted tree: ' + str(path))
    parent = path
    while not parent.exists():
        parent = parent.parent
    if not os.access(parent, os.W_OK | os.X_OK if parent.is_dir() else os.W_OK):
        raise ValueError('write/scratch parent not writable: ' + str(parent))
    return resolved


def kd_scratch(out, build):
    root = Path(out) / 'host-reference'
    inside(Path(out), build, tree=True)
    inside(root, build, tree=True)
    inside(Path(out) / 'host-reference.jsonl.gz', build)
    inside(Path(out) / 'host-reference.jsonl.gz.tmp', build)
    return root


def inventory(packet, build, out, windows, prompts):
    """Directories cover all native dynamic descendants; inspect existing trees too."""
    packet, build, out = map(Path, (packet, build, out))
    rows, errors = [], []
    def add(name, role, path, boundary, tree=False):
        row = dict(window=name, role=role, path=str(path), boundary=str(boundary.resolve()))
        try:
            row['resolved'] = str(inside(path, boundary, tree=tree))
            row['passed'] = True
        except (OSError, ValueError) as error:
            row.update(passed=False, error=str(error)); errors.append(str(error))
        rows.append(row)
    for name in windows:
        root = out / name
        add(name, 'lane admission sidecar', out / (name + '-lane-admission.json'), out)
        add(name, 'lane admission atomic UUID temporary', out / (name + '-lane-admission.json.UUID.tmp'), out)
        add(name, 'window atomic UUID temporary', root / 'window.json.UUID.tmp', root)
        add(name, 'private driver home', root / 'driver-home', root, True)
        add(name, 'window output and dynamic descendants', root, out, True)
        for leaf in ('window.json', 'retention.json', 'children.json', 'failure-before-teardown.json', 'retained.json'):
            add(name, 'receipt/retention', root / leaf, root)
        add(name, 'queue log', out / (name + '.log'), out)
        dirs = (('run0','run1') if name == 'K0' else
                ('run0','linked','qsa','expert','round2','round3') if name in ('K1a','K1b') else
                ('run0','round3-timing') if name == 'K2' else
                ('host-reference','owner0','owner1') if name == 'KD' else ('run',))
        for leaf in dirs:
            add(name, 'owner/fixture scratch', root / leaf, root)
            add(name, 'compressed retention', root / (leaf + '.log.gz'), root)
        if name == 'KD':
            # Audit siblings against THEIR current rule, not the repaired 61x rule.
            kd_boundary = build if packet.name == 'packet75-record-bundle' else (packet / 'build').resolve()
            for leaf in ('host-reference','host-reference.jsonl.gz','host-reference.jsonl.gz.tmp'):
                add(name, 'KD host-reference admission', root / leaf, kd_boundary)
        if name.startswith('W'):
            for rank in (0,1):
                add(name, 'driver cache', root / 'run/driver-cache' / f'rank{rank}', root, True)
                add(name, 'suite driver cache', root / 'run/ranks/driver-cache' / f'rank{rank}', root, True)
                add(name, 'rank owner', root / 'run' / f'rank{rank}', root)
                add(name, 'suite rank owner', root / 'run/ranks' / f'rank{rank}', root)
        if name.startswith('WS'):
            for prompt in prompts:
                for path in (root/'run/input-bundles'/prompt, root/'run/repeat-1'/prompt):
                    add(name, 'suite input/fixture/state retention', path, root)
            add(name, 'warmup scratch', root / 'run/warmup', root)
    for leaf in ('queue.lock','queue-state.json','running.json','waiting.json','STOP',
                 'resume-manifest.json','prefix-head-prerequisites.json','queue-all-complete.json',
                 'queue-model-complete.json','queue-early-complete.json'):
        add('K0', 'queue state (including atomic temporary)', out / leaf, build)
        add('K0', 'queue atomic temporary', out / (leaf + '.tmp'), build)
    # These are the two intentionally shared protocol locations. Enumerate
    # their exact files; no general external scratch directory is admitted.
    from lane_admission import DEFAULT_ROOT
    from drain_gate import DEFAULT_DRAIN_ROOT
    for leaf in ('protocol.lock','lane-A.lock','lane-B.lock','active-lane-A.json','hold-lane-B'):
        add('K0', 'shared lane protocol', DEFAULT_ROOT / leaf, DEFAULT_ROOT)
        if not leaf.endswith('.lock'):
            add('K0', 'shared lane atomic UUID temporary', DEFAULT_ROOT / (leaf+'.UUID.tmp'), DEFAULT_ROOT)
    for leaf in ('teardown.lock','teardown-state.json','teardown-state.json.UUID.tmp'):
        add('K0', 'shared drain protocol', DEFAULT_DRAIN_ROOT / leaf, DEFAULT_DRAIN_ROOT)
    return rows, errors

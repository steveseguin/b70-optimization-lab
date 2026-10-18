"""One pinned early-window import. Never imports or executes a model window."""
import json
from pathlib import Path
import shutil
from storage import digest, B, REGISTERED_CHAIN, admit
from write_paths import inside

P = Path(__file__).resolve().parent
EARLY = ('K0', 'K1a', 'K1b', 'K2', 'W0p')
LATE = ('KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128')


def require(value, message):
    if not value:
        raise ValueError('resume refused: ' + message)


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def pins():
    return json.loads((P / 'resume-pins.json').read_text())


def file_inventory(root):
    files = {str(f.relative_to(root)): digest(f) for name in EARLY
             for f in sorted((root / name).rglob('*')) if f.is_file()}
    for name in EARLY:
        path = root / (name + '-lane-admission.json')
        if path.is_file(): files[path.name] = digest(path)
    return files


def validate(source, destination=None, *, prepared=False):
    pin = pins(); source = Path(source).absolute()
    require(str(source) == pin['source'], 'source is not the pinned stopped chain')
    require(pin['windows'] == list(EARLY), 'only the five early windows may be imported')
    require(boot_id() == pin['boot_id'], 'boot changed')
    require(digest(P / pin['old_seal_path']) == pin['old_seal_sha256'], 'original wrapper seal changed')
    require(digest(P / 'screen-seal.json') == pin['screen_seal_sha256'], 'screen seal changed')
    current = json.loads((P / 'build-receipt.json').read_text())
    require(current['sources'].get(str((P / 'resume-pins.json').relative_to(P.parents[3]))) == digest(P / 'resume-pins.json'), 'resume pins are not sealed')
    old = json.loads((P / pin['old_seal_path']).read_text())
    require({k:v for k,v in old.items() if k != 'sources'} == {k:v for k,v in current.items() if k != 'sources'}, 'non-wrapper seal identity changed')
    require(current['artifacts_sha256'] == pin['artifacts_sha256'], 'artifact identity changed')
    for name, expected in pin['artifacts_sha256'].items():
        require(digest(P / 'build' / name) == expected, 'binary changed: ' + name)
    require(digest(P / 'dispatch-p45.json') == pin['candidate_dispatch_sha256'], 'candidate dispatch changed')
    for name in EARLY:
        inside(source / name, source, tree=True)
    expected_files = {name: value for name, value in pin['files'].items()
                      if name.split('/')[0] in EARLY or name in {n+'-lane-admission.json' for n in EARLY}}
    require(expected_files == pin['files'], 'non-early file in resume inventory')
    require(file_inventory(source) == expected_files, 'early receipt/file hash or inventory changed')
    for name, expected in pin['files'].items():
        require(digest(source / name) == expected, 'source receipt hash changed: ' + name)
    require(digest(source / 'K2/run0/dispatch-measured.json') == pin['dispatch_sha256'], 'measured dispatch changed')
    from queue_runner import validate_success
    from window import prerequisites
    first = json.loads((source / 'K0/window.json').read_text())
    for name in EARLY:
        validate_success(name, source, 0)
        row = prerequisites(source / name / 'window.json', name, first)
        if 'lane_admission' in row:
            require(Path(row['lane_admission']['path']) == source / (name+'-lane-admission.json'),
                    'early admission sidecar outside pinned source')
        require(row['boot_id'] == pin['boot_id'] and row['build_receipt_sha256'] == pin['old_seal_sha256'], 'old receipt identity changed')
        require(row['artifacts_sha256'] == pin['artifacts_sha256'] and row['screen_seal_sha256'] == pin['screen_seal_sha256'], 'receipt binary/seal changed')
    require(json.loads((source/'K2/window.json').read_text())['dispatch_sha256'] == pin['dispatch_sha256'], 'receipt dispatch changed')
    manifest = dict(schema='packet91.resume-manifest.v1', source=str(source),
                    boot_id=pin['boot_id'], imported_windows=list(EARLY), fresh_windows=list(LATE),
                    resume_pins_sha256=digest(P/'resume-pins.json'),
                    original_build_receipt_sha256=pin['old_seal_sha256'],
                    current_build_receipt_sha256=digest(P/'build-receipt.json'),
                    screen_seal_sha256=pin['screen_seal_sha256'], artifacts_sha256=pin['artifacts_sha256'],
                    dispatch_sha256=pin['dispatch_sha256'], files=expected_files, method='copy; original receipt bytes unchanged')
    if destination is not None:
        destination = Path(destination).absolute()
        expected_destination = Path(pin.get('destination', str(B / REGISTERED_CHAIN)))
        require(destination == expected_destination and destination.parent == B and destination != source, 'destination is not fresh registered/pinned chain')
        inside(destination, B)
        manifest['destination'] = str(destination)
        if prepared:
            require(json.loads((destination/'resume-manifest.json').read_text()) == manifest, 'resume manifest changed')
            for name in EARLY:
                inside(destination/name, destination, tree=True)
            require(file_inventory(destination) == expected_files, 'copied receipt/file hash changed')
    return manifest


def prepare(source, destination):
    manifest = validate(source, destination)
    destination = Path(destination)
    require(not destination.exists(), 'destination already exists; no overwrite')
    admit(sum((Path(source)/name).stat().st_size for name in manifest['files']) + 1_000_000)
    destination.mkdir(parents=True)
    try:
        for name in EARLY:
            shutil.copytree(Path(source)/name, destination/name, copy_function=shutil.copyfile)
            sidecar = Path(source)/(name+'-lane-admission.json')
            if sidecar.exists(): shutil.copyfile(sidecar, destination/sidecar.name)
        (destination/'resume-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        validate(source, destination, prepared=True)
    except BaseException as error:
        (destination/'STOP').write_text('resume preparation failed: '+str(error)+'\n')
        raise
    return manifest


def prerequisite_seal(path, identity):
    """Narrow exception for untouched imported receipts, never for late windows."""
    path = Path(path).absolute(); destination = path.parent.parent
    require(path.parent.name in EARLY and path.name == 'window.json', 'model receipts must be fresh')
    manifest = validate(Path(pins()['source']), destination, prepared=True)
    require(identity['build_receipt_sha256'] == manifest['current_build_receipt_sha256'], 'active wrapper seal differs')
    require(identity['boot_id'] == manifest['boot_id'], 'active boot differs')
    return manifest['original_build_receipt_sha256']

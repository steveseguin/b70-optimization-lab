import hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'.git').is_dir())
ORACLE=ROOT/'experiments/own-xpu-runtime/stage2/packet49-integrate/oracle'
ARITHMETIC='iq3-p49-split32-v1'
SUITE_SHA='0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
spec=importlib.util.spec_from_file_location('packet163_oracle_checker',HERE/'oracle_check.py')
CHECK=importlib.util.module_from_spec(spec);spec.loader.exec_module(CHECK)
def oracle_inputs():
    """Verify sealed completion and original input bytes without model payload reads."""
    binding = read(HERE / 'oracle-binding.json')
    for row in binding['parent_records']:
        name,digest=row['parent_relpath'],row['parent_digest']
        require(sha(ROOT / name) == digest, 'oracle source binding: ' + name)
    require(sha(ORACLE/'results/completion.json')==binding['completion_sha256'], 'registered oracle completion changed')
    completion = read(ORACLE / 'results/completion.json')
    require(completion['passed'] is True and completion['device_executed'] is False
            and completion['arithmetic'] == ARITHMETIC and completion['prompts'] == 12
            and completion['token_cap'] == 128, 'incomplete registered oracle')
    for key, leaf in [('manifest_sha256','suite-manifest.json'), ('determinism_sha256','determinism.json'),
                      ('kd_capture_sha256','kd-capture.json'), ('old_v_new_sha256','old-v-new.json')]:
        require(sha(ORACLE / 'results' / leaf) == completion[key], 'oracle completion pin')
    require(sha(ORACLE/'build-receipt.json')==completion['build_receipt_sha256'], 'oracle build pin')
    manifest = read(ORACLE/'results/suite-manifest.json')
    require(manifest.get('complete') is True and manifest['arithmetic']==ARITHMETIC
            and manifest['suite_sha256']==SUITE_SHA and manifest['token_cap']==128
            and manifest['context']==4096, 'oracle suite identity')
    require([e['prompt_id'] for e in manifest['prompts']]==list(CHECK.PROMPT_IDS), 'full fixed prompt order')
    for entry in manifest['prompts']:
        bundle = (ROOT/entry['input_bundle']).resolve()
        require(bundle.is_relative_to(ROOT), 'input bundle escapes repository')
        for leaf,digest in entry['input_bundle_hashes'].items():
            require(Path(leaf).name==leaf and sha(bundle/leaf)==digest, 'input bundle hash')
        expected=ORACLE/'results'/entry['prompt_id']
        require(sha(expected/'receipt.json')==entry['oracle_receipt_sha256'], 'oracle request pin')
        receipt=read(expected/'receipt.json')
        require(receipt.get('verified') is True and sha(expected/'result.json')==receipt['result_sha256']
                and sha(expected/'validation.json')==receipt['validation_sha256'], 'oracle output binding')
    return manifest


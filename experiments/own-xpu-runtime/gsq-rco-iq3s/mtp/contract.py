"""Strict metadata compatibility, not target kernel or MTP acceptance admission."""
from pathlib import Path
import hashlib
import json
import stat

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
DRAFT_ROOT = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def validate_contract(old, new):
    """Pure comparison; caller binds whole census bytes before calling."""
    a, b = old['metadata'], new['metadata']
    keys = lambda m: {k for k in m if k.startswith(('qwen4exp.', 'tokenizer.'))
                      or k == 'general.architecture'}
    require(keys(a) == keys(b), 'architecture/tokenizer metadata key set')
    for key in sorted(keys(a)):
        require(a[key] == b[key], 'architecture/tokenizer mismatch: ' + key)
    values = {'general.architecture':'qwen4exp', 'qwen4exp.embedding_length':2560,
              'qwen4exp.block_count':48, 'qwen4exp.expert_count':512,
              'qwen4exp.hyper_connection.count':4,
              'qwen4exp.hyper_connection.low_rank':320,
              'qwen4exp.ple.eos_token_id':248044,
              'tokenizer.ggml.eos_token_id':248046}
    for key, expected in values.items():
        observed = b[key]['value']
        require(type(observed) is type(expected) and observed == expected,
                'fixed draft geometry/token contract: ' + key)
    for name in ('token_embd.weight', 'output.weight'):
        for census in (old, new):
            t = census['tensors'][name]
            require(t['shape'] == [248320, 2560] and
                    t['dimensions'] == [2560, 248320] and
                    t['payload_extent_validated'] is True,
                    'shared target embedding/head shape/extent: ' + name)
    tokens = b['tokenizer.ggml.tokens']['value']
    require(tokens['kind'] == 'array' and type(tokens['count']) is int and
            tokens['count'] == 248320, 'token vocabulary')
    require(new['tensors']['token_embd.weight']['type'] == 'IQ4_XS',
            'new target embedding format')
    require(new['tensors']['output.weight']['type'] == 'Q6_K', 'target head format')
    return dict(metadata_compatible=True, native_admitted=False,
                draft_tensor_count=3101, hidden_shape=[4,2560],
                hidden_bytes_bf16=20480, vocab=248320,
                matched_metadata_keys=sorted(keys(a)),
                confirmed_input='H_(p-1), confirmed x_p, draft cache/RoPE position p-1',
                target_embedding_decoder_required='IQ4_XS',
                embedding_payload_equality_claimed=False,
                draft_head_policy='full vocabulary for first new-model admission; old 80128 prefix calibration not transferred',
                limits='metadata compatibility only; target format kernels, memory/placement, live owner, real hidden-state MTP and acceptance remain unqualified')


def draft_inventory():
    audit = json.loads((P/'source-audit.json').read_text())
    manifest = ROOT / audit['draft_manifest']
    require(sha(manifest) == audit['source_sha256'][audit['draft_manifest']],
            'draft manifest changed')
    rows = [line.split() for line in manifest.read_text().splitlines() if line]
    require(len(rows) == 3101 and len({r[0] for r in rows}) == 3101,
            'exact draft tensor set')
    files = {}
    for r in rows:
        require(len(r) == 13 and r[0].startswith('mtp.') and
                Path(r[1]).name == r[1], 'draft manifest record')
        offset, size = int(r[2]), int(r[3])
        expected = dict(zip(('size','device','inode','mtime_ns','ctime_ns'), map(int,r[8:13])))
        require(0 < size <= 64*1024**2 and 0 <= offset <= expected['size']-size,
                'draft tensor bounds')
        require(r[4] in ('BF16','F8_E4M3') and int(r[5]) > 0 and int(r[6]) > 0,
                'draft dtype/geometry')
        require(size == int(r[5])*int(r[6])*(2 if r[4]=='BF16' else 1),
                'draft tensor encoded extent')
        if r[1] in files:
            require(files[r[1]]['expected'] == expected, 'inconsistent file identity')
            continue
        path = DRAFT_ROOT / r[1]
        s = path.lstat()
        require(stat.S_ISREG(s.st_mode) and path.resolve().parent == DRAFT_ROOT.resolve(),
                'draft regular local file')
        actual = dict(size=s.st_size, device=s.st_dev, inode=s.st_ino,
                      mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)
        require(actual == expected, 'draft file identity changed: ' + r[1])
        files[r[1]] = dict(path=str(path), realpath=str(path.resolve()),
                          expected=expected, observed=actual)
    require(len(files) == 28, 'draft file count')
    return dict(passed=True, tensor_count=3101, file_count=28,
                tensor_bytes=sum(int(r[3]) for r in rows), files=files,
                tensor_manifest_copy='draft-manifest.tsv',
                tensor_payload_bytes_read=0, payload_hashes_recomputed=False,
                scope='stat identity only; per-tensor hashes are historical manifest claims; native loader rechecks tensor payload hashes at load')


def bound_contract():
    bindings = json.loads((P/'target-bindings.json').read_text())
    for relative, digest in bindings['sha256'].items():
        require(sha(ROOT/relative) == digest, 'target metadata binding changed: '+relative)
    old = json.loads((ROOT/bindings['old']).read_text())
    new = json.loads((ROOT/bindings['new']).read_text())
    return validate_contract(old,new)

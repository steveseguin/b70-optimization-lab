"""Packet184 CPU gate: real two-rank host-only sessions with the two-card checkpoint.

Every session is the packet's gnu-host engine (v5/build/gnu-host/own-rt-iq3) launched as TWO rank
processes by the vendored packet56 pipeline.Transport (--mini geometry, the MTP draft on rank 1,
v5/lineage/mini/selection.json = bundle 8 with the two production-geometry-only choices relaxed).
Checkpoint commit/inspect/delete run the device-free tool binary (v5/build/tool/own-rt-ckpt-tool).
No device, no model weights; writes only under v5/build/cpu-gate (removed at the end) and the receipt
v5/evidence/checkpoint-cpu.json.

Gates (each a hard assertion):
  lifecycle  for (K, M) in (8,6) (27,9) (28,9) (30,12) -- N = 12, 31, 32, 34 crosses the 32-row
             launch-extent bucket and partial pooled quads: save at K in one pair, restore in a
             FRESH pair, resume M, save again. The merged token stream and the merged draft guess
             stream equal one uninterrupted K+M run; every saved blob of BOTH ranks (KV slices, GDN
             and PLE banks incl. spare/reserve, controls, rank-1 boundary stream, draft KV/controls)
             is byte-identical to a save of the uninterrupted run at the same position. A second,
             independent restore of the same checkpoint repeats tokens and blobs exactly.
  append     restore S1 + append a 7-token and a 25-token delta (crossing 32) + generate, save
             (restore-then-save): tokens and blobs equal a fresh one-shot run of the new input saved
             at the same position; restore that child, resume, save again == one-shot reference
             (chain); an empty-delta append equals the same-generation resume.
  coverage   at one boundary the engine's own state dump + request_state_inventory + draft
             dump_all_state are taken, then the checkpoint is staged: the labels classified by the
             checkpoint equal the union of the three dumps exactly (fail-closed both ways), every
             inventory host field has a rule, and every saved blob equals the dump's bytes.
  draft      a forged copy of S1 whose draft KV blobs are zeroed (resealed so it verifies) restores
             the target exactly (target blobs and tokens equal) but leaves the draft cache rows zero
             (draft blobs differ): the draft cache is not rebuilt from the target state, so it is saved.
  refusals   forged/tampered/missing/mismatched checkpoints and wrong inputs; each refused with the
             expected check before any upload (precheck tool and rank-side verify both exercised).
  locks      sibling-lock protocol between the Python coordinator, the C++ tools and the ranks.
CPU limits: nice 19, cores 8-15,24-31, CPU disk stop 27 GB free (packet181 precedent). Every rank
pair has the pipeline's own bounded waits (--wait-seconds 300, --seconds 600); the whole gate has a
3600 s deadline (measured runtime is recorded in the receipt).
"""
import contextlib, hashlib, json, os, resource, shutil, struct, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tp2_checkpoint as T
from p184_build_checkpoint import sha, save, limits, ROOT

ENGINE = HERE / 'build/gnu-host/own-rt-iq3'
TOOL = HERE / 'build/tool/own-rt-ckpt-tool'
SEL = HERE / 'lineage/mini/selection.json'
TOK = HERE / 'tokenizer-identity.tsv'
W = HERE / 'build/cpu-gate'
DEADLINE = time.monotonic() + 3600
PROMPT = [2, 5, 3, 7, 1]
CASES = []


def check(ok, message):
    if not ok:
        raise AssertionError(message)
    assert time.monotonic() < DEADLINE, 'CPU gate deadline (3600 s) exceeded'


def record(name, **row):
    CASES.append(dict(case=name, **row))
    print('PASS', name, flush=True)


def open_pair(name):
    limits()
    p = T.open_pair(T.cpu_args(ENGINE, W / 'pairs' / name), W / 'pairs' / name, ENGINE, TOK, True, SEL)
    p.binary = TOOL                    # host tools from the device-free tool binary
    return p


def close(p, ok=True):
    if ok:
        p.t.close(True)
    else:
        try:
            p.t.stop('cpu gate')
        finally:
            p.t.close(False)


@contextlib.contextmanager
def session(name):
    p = open_pair(name)
    ok = False
    try:
        yield p
        ok = True
    finally:
        close(p, ok)


def guesses(result):
    return [d['guess'] for d in result['draft_rows']]


def blobs(root, cid):
    m = json.loads((root / cid / 'manifest.json').read_text())
    return m, {(rs['rank'], b['name']): b['sha256'] for rs in m['ranks'] for b in rs['blobs']}


def fresh(name, root, prompt, count, save_id=None, dump=False):
    with session(name) as p:
        p.reset(W / 'requests' / name)
        r = p.request(prompt, count)
        if dump:
            p.dump()
        s = p.save(root, save_id, len(prompt)) if save_id else None
        hist, pend = list(p.history), p.pending
    return r, s, hist, pend


def restored(name, root, cid, inp, count, save_id=None, precheck=True, hold_lock=True):
    with session(name) as p:
        rec, prompt = p.restore(root, cid, inp, count, W / 'requests' / name, precheck, hold_lock)
        r = p.request(prompt, count, rec['position'])
        s = p.save(root, save_id, len(inp), parent=rec) if save_id else None
    return rec, r, s


def same_state(root, a, b, what):
    ma, ba = blobs(root, a)
    mb, bb = blobs(root, b)
    check(set(ba) == set(bb), what + ': blob sets differ')
    diff = sorted(f'rank{k[0]}/{k[1]}' for k in ba if ba[k] != bb[k])
    check(not diff, what + ': blobs differ ' + str(diff[:8]))
    for k in ('position', 'next_token', 'tokens_sha256', 'token_history'):
        check(ma['token_state'][k] == mb['token_state'][k], what + ': token_state.' + k)
    check(ma['draft']['position'] == mb['draft']['position'], what + ': draft position')
    return len(ba), sum(b['bytes'] for rs in ma['ranks'] for b in rs['blobs'])


def reseal(d, edits=(), tsv=()):
    """Test-only forger: edit manifest.json text, then keep fields.tsv consistent (sha row + rows)."""
    text = (d / 'manifest.json').read_text()
    for a, b in edits:
        check(text.count(a) == 1, 'forge anchor ' + a[:60])
        text = text.replace(a, b)
    (d / 'manifest.json').write_text(text)
    rows = (d / 'fields.tsv').read_text()
    for a, b in tsv:
        check(rows.count(a) == 1, 'forge tsv anchor ' + a[:60])
        rows = rows.replace(a, b)
    lines = [('manifest_sha256\t' + hashlib.sha256(text.encode()).hexdigest()) if l.startswith('manifest_sha256\t') else l
             for l in rows.split('\n')]
    (d / 'fields.tsv').write_text('\n'.join(lines))


def rewrite_blob(d, rank, name, data):
    path = d / f'rank{rank}' / (name + '.bin')
    old = sha(path)
    path.write_bytes(data)
    new = hashlib.sha256(data).hexdigest()
    reseal(d, [(old, new)], [(old, new)])


def lifecycle(root):
    out = []
    for K, M in ((8, 6), (27, 9), (28, 9), (30, 12)):
        tag = f'{K}-{M}'
        r, _, _, _ = fresh('ref-' + tag, root, PROMPT, K + M, 'ref-' + tag)
        s, s1, hist, pend = fresh('save-' + tag, root, PROMPT, K, 's1-' + tag)
        rec, x, _ = restored('resume-' + tag, root, 's1-' + tag, PROMPT, M, 's2-' + tag)
        check(rec['operation'] == 'same-generation-resume' and rec['position'] == len(PROMPT) + K - 1, tag + ': restore record')
        check(s['tokens'] + x['tokens'] == r['tokens'], tag + ': merged tokens differ from the uninterrupted run')
        check(guesses(s) + guesses(x) == guesses(r), tag + ': merged draft guesses differ')
        n, nbytes = same_state(root, 's2-' + tag, 'ref-' + tag, tag + ' resume vs uninterrupted')
        rec2, x2, _ = restored('repeat-' + tag, root, 's1-' + tag, PROMPT, M, 's2b-' + tag)
        check(x2['tokens'] == x['tokens'] and guesses(x2) == guesses(x), tag + ': repeat restore differs')
        same_state(root, 's2b-' + tag, 's2-' + tag, tag + ' repeat restore')
        out.append(dict(K=K, M=M, N=rec['position'], tokens=len(r['tokens']), guesses=len(guesses(r)), blobs=n, saved_bytes=nbytes,
                        restore_seconds=rec['restore_seconds'], restored_bytes=rec['restored_bytes'], save_seconds=s1['seconds']))
        record('lifecycle ' + tag, N=rec['position'], blobs=n, merged_tokens=len(r['tokens']))
    return out


def append(root):
    rows = []
    _, _, hist, pend = fresh('append-base', root, PROMPT, 8, 'a-s1')
    for label, delta in (('delta7', [4, 9, 2, 11, 6, 3, 8]), ('delta25', [(3 * i + 1) % 15 for i in range(25)])):
        new = hist + [pend] + delta
        ref, _, _, _ = fresh('append-ref-' + label, root, new, 6, 'a-ref-' + label)
        rec, x, _ = restored('append-' + label, root, 'a-s1', new, 6, 'a-s3-' + label)
        check(rec['operation'] == 'append' and rec['appended_length'] == len(delta), label + ': append record')
        check(x['tokens'] == ref['tokens'], label + ': append tokens differ from the one-shot run')
        check(guesses(ref)[-len(guesses(x)):] == guesses(x), label + ': post-restore draft guesses differ from the one-shot run')
        n, _ = same_state(root, 'a-s3-' + label, 'a-ref-' + label, label + ' append vs one-shot')
        m3 = json.loads((root / ('a-s3-' + label) / 'manifest.json').read_text())
        check(m3['lineage']['operation'] == 'restore-then-save' and m3['lineage']['parent']['checkpoint_id'] == 'a-s1', label + ': lineage')
        # chain: restore the restore-then-save child, resume 5, save; equals one-shot new+6+5
        chain_ref, _, _, _ = fresh('chain-ref-' + label, root, new, 11, 'a-chain-ref-' + label)
        rec4, y, _ = restored('chain-' + label, root, 'a-s3-' + label, new, 5, 'a-s4-' + label)
        check(x['tokens'] + y['tokens'] == chain_ref['tokens'], label + ': chain tokens differ')
        same_state(root, 'a-s4-' + label, 'a-chain-ref-' + label, label + ' chain vs one-shot')
        rows.append(dict(delta=len(delta), N=rec['position'], new_length=len(new), blobs=n, chain_position=rec4['position']))
        record('append ' + label, N=rec['position'], new_length=len(new))
    # empty-delta append == same-generation resume
    rec_e, xe, _ = restored('append-empty', root, 'a-s1', hist + [pend], 6, 'a-empty')
    rec_r, xr, _ = restored('append-empty-resume', root, 'a-s1', PROMPT, 6, 'a-empty-resume')
    check(rec_e['operation'] == 'append' and rec_e['appended_length'] == 0 and rec_r['operation'] == 'same-generation-resume', 'empty delta records')
    check(xe['tokens'] == xr['tokens'] and guesses(xe) == guesses(xr), 'empty-delta append differs from resume')
    same_state(root, 'a-empty', 'a-empty-resume', 'empty-delta append vs resume')
    record('append empty-delta == resume')
    return rows


def coverage(root):
    r, s, _, _ = fresh('coverage', root, PROMPT, 10, 'cov', dump=True)
    req = W / 'requests' / 'coverage'
    rows = []
    for rank in (0, 1):
        rd = req / f'rank{rank}'
        state = json.loads((rd / 'state-2147483647/state.json').read_text())
        inv = json.loads((rd / 'request-state-inventory.json').read_text())
        labels = set(state['buffers']) | set(inv['standalone_target_mutable'])
        draft = None
        if rank == 1:
            draft = json.loads((rd / 'draft-final-state/all-state.json').read_text())
            labels |= set(draft['mutable_sha256'])
        cov = s['coverage'][rank]
        covered = [c['label'] for c in cov]
        check(len(covered) == len(set(covered)), f'rank{rank}: a label is classified twice')
        check(set(covered) == labels, f'rank{rank}: coverage differs from the inventory: '
              f'unclassified {sorted(labels - set(covered))[:5]} extra {sorted(set(covered) - labels)[:5]}')
        host = {h['field'] for h in s['host_fields'][rank]}
        inv_host = set(inv) - {'standalone_target_mutable'}
        check(inv_host <= host, f'rank{rank}: inventory host fields without a rule {sorted(inv_host - host)}')
        check(host - inv_host == {'draft.position', 'draft.disabled', 'draft.context_extent'}, f'rank{rank}: host field set')
        if draft:
            check({'position', 'disabled'} <= set(draft), 'draft dump host fields')
        # every saved blob equals the engine's own dump bytes at the same boundary
        m = json.loads((root / 'cov' / 'manifest.json').read_text())
        compared = 0
        for b in m['ranks'][rank]['blobs']:
            data = (root / 'cov' / f'rank{rank}' / (b['name'] + '.bin')).read_bytes()
            if b['source'] == 'plan':
                ref = (rd / 'state-2147483647' / (b['name'] + '.bin')).read_bytes()
            elif b['source'] == 'spare':
                ref = (rd / 'state-2147483647' / ('alternate-' + b['name'][len('spare.'):] + '.bin')).read_bytes()
            elif b['source'] == 'reserve':
                check(hashlib.sha256(data).hexdigest() == inv['standalone_target_mutable']['0:speculative-reserve:' + b['name'][len('reserve.'):]]['sha256'],
                      'reserve bytes differ from the inventory hash ' + b['name'])
                compared += 1
                continue
            else:
                name = b['name'][len('draft.'):]
                path = rd / 'draft-final-state' / (name + '.bin')
                if not path.exists():  # the draft dump writes the KV family and position only
                    label = next(c['label'] for c in cov if c['source'] == 'draft' and c['label'].endswith(':draft:' + name))
                    check(hashlib.sha256(data).hexdigest() == draft['mutable_sha256'][label], 'draft control bytes ' + name)
                    compared += 1
                    continue
                ref = path.read_bytes()
            check(ref[:len(data)] == data, f'rank{rank}: blob {b["name"]} differs from the engine state dump')
            compared += 1
        check(compared == len(m['ranks'][rank]['blobs']), 'every blob compared')
        rows.append(dict(rank=rank, labels=len(labels), saved=len(m['ranks'][rank]['blobs']),
                         skipped=len(m['ranks'][rank]['skipped']), host_fields=len(host), blobs_byte_compared=compared))
    record('coverage == inventory (both ranks)', ranks=rows)
    return rows


def draft_necessity(root):
    ref, _, _, _ = fresh('draft-ref', root, PROMPT, 14, 'd-ref')
    s, _, _, _ = fresh('draft-save', root, PROMPT, 8, 'd-s1')
    shutil.copytree(root / 'd-s1', root / 'd-zero')
    m = json.loads((root / 'd-zero' / 'manifest.json').read_text())
    text = (root / 'd-zero' / 'manifest.json').read_text()
    (root / 'd-zero' / 'manifest.json').write_text(text.replace('"checkpoint_id":"d-s1"', '"checkpoint_id":"d-zero"', 1))
    reseal(root / 'd-zero', (), [('checkpoint_id\td-s1', 'checkpoint_id\td-zero')])
    zeroed = []
    for b in m['ranks'][1]['blobs']:
        if b['source'] == 'draft' and '.qsa.' in b['name']:
            rewrite_blob(root / 'd-zero', 1, b['name'], bytes(b['bytes']))
            zeroed.append(b['name'])
    code, ins = T.tool(TOOL, '--checkpoint-inspect', root / 'd-zero')
    check(code == 0 and ins['ok'], 'forged zero-draft checkpoint must verify (positive forger control)')
    rec, x, _ = restored('draft-zero', root, 'd-zero', PROMPT, 6, 'd-zero-s2')
    check(s['tokens'] + x['tokens'] == ref['tokens'], 'target tokens must still equal (the target verifies every draft guess)')
    _, bref = blobs(root, 'd-ref')
    _, bz = blobs(root, 'd-zero-s2')
    target_diff = sorted(k for k in bref if not k[1].startswith('draft.') and bref[k] != bz.get(k))
    draft_diff = sorted(k[1] for k in bref if k[1].startswith('draft.') and bref[k] != bz.get(k))
    check(not target_diff, 'target state differs after a zero-draft restore: ' + str(target_diff[:5]))
    check(set(zeroed) <= set(draft_diff), 'zeroed draft rows were rebuilt (unexpected): ' + str(draft_diff))
    row = dict(zeroed=zeroed, draft_blobs_differing_after_resume=draft_diff, target_blobs_equal=True,
               merged_tokens_equal=True, guesses_equal=guesses(s) + guesses(x) == guesses(ref),
               conclusion='continuing from the saved target state does not regenerate draft KV rows [0, N-1); the draft cache must be saved')
    record('draft state is saved, not rebuilt', **{k: v for k, v in row.items() if k != 'conclusion'})
    return row


def refusals(root):
    _, base, hist, pend = fresh('refusal-base', root, PROMPT, 8, 'r-base')
    rows = []
    serial = [0]

    def copy(edit=None):
        serial[0] += 1
        cid = f'r-{serial[0]:02d}'
        shutil.copytree(root / 'r-base', root / cid)
        text = (root / cid / 'manifest.json').read_text()
        (root / cid / 'manifest.json').write_text(text.replace('"checkpoint_id":"r-base"', f'"checkpoint_id":"{cid}"', 1))
        reseal(root / cid, (), [('checkpoint_id\tr-base', f'checkpoint_id\t{cid}')])
        if edit:
            edit(root / cid)
        return cid

    def expect(name, cid, check_name, inp=PROMPT, count=4, precheck=True, hold_lock=True, where='precheck'):
        try:
            restored('refuse-' + cid, root, cid, inp, count, precheck=precheck, hold_lock=hold_lock)
        except T.Refused as error:
            check(error.check == check_name, f'{name}: refused by {error.check!r} ({error.detail}) not {check_name!r}')
            req = W / 'pairs' / ('refuse-' + cid)
            applied = [p.name for r in (0, 1) for p in (req / f'rank{r}').glob('checkpoint-*.json')
                       if json.loads(p.read_text()).get('schema') == 'packet184.rank-restore-apply.v1']
            check(not applied, name + ': a rank applied a restore before the refusal')
            rows.append(dict(case=name, refused_by=error.check, rank=error.rank, where=where, detail=error.detail[:160], uploads=0))
            print('PASS refusal', name, '->', error.check, flush=True)
            return
        raise AssertionError(name + ': not refused')
    flip = lambda rank, name: (lambda d: (lambda p: p.write_bytes(bytes([p.read_bytes()[0] ^ 1]) + p.read_bytes()[1:]))(d / f'rank{rank}' / (name + '.bin')))
    expect('rank0 blob byte (precheck)', copy(flip(0, 'blk.1.qsa.keys')), 'blob sha256')
    expect('rank0 blob byte (rank verify)', copy(flip(0, 'blk.1.qsa.keys')), 'blob sha256', precheck=False, where='rank 0 verify')
    expect('rank1 draft blob byte (rank verify)', copy(flip(1, 'draft.blk.0.qsa.keys')), 'blob sha256', precheck=False, where='rank 1 verify')
    expect('rank0 spare bank byte (rank verify)', copy(flip(0, 'spare.blk.0.gdn.state')), 'blob sha256', precheck=False, where='rank 0 verify')
    expect('rank1 set missing', copy(lambda d: shutil.rmtree(d / 'rank1')), 'file set')
    expect('rank1 set missing (rank verify)', copy(lambda d: shutil.rmtree(d / 'rank1')), 'file set', precheck=False, where='rank verify')
    expect('rank sets swapped', copy(lambda d: (os.rename(d / 'rank0', d / 'x'), os.rename(d / 'rank1', d / 'rank0'), os.rename(d / 'x', d / 'rank1'))), 'file set')
    expect('extra file in rank0', copy(lambda d: (d / 'rank0' / 'junk.bin').write_bytes(b'x')), 'file set')
    expect('fields.tsv host value (history0)', copy(lambda d: (d / 'fields.tsv').write_text(
        (d / 'fields.tsv').read_text().replace(f'history0\t{hist[-2]}\n', f'history0\t{hist[-2] + 1}\n', 1))), 'manifest cross-check')
    expect('manifest field edited, unsealed (created)', copy(lambda d: (d / 'manifest.json').write_text(
        __import__('re').sub(r'"created":"[^"]*"', '"created":"1999-01-01T00:00:00Z"', (d / 'manifest.json').read_text(), count=1))), 'manifest sha256')
    expect('manifest host value, unsealed (token_history)', copy(lambda d: (d / 'manifest.json').write_text(
        (d / 'manifest.json').read_text().replace(f'"token_history":[{hist[-2]},{hist[-1]}]', f'"token_history":[{hist[-2]},{hist[-1] + 1}]', 1))), 'manifest')
    h0, h1, h1x = hist[-2], hist[-1], (hist[-1] + 1) % 16
    q0 = ','.join(map(str, json.loads((root / 'r-base/manifest.json').read_text())['ranks'][0]['qsa_layers']))
    g0 = ','.join(map(str, json.loads((root / 'r-base/manifest.json').read_text())['ranks'][0]['gdn_layers']))
    expect('host value resealed consistently (token_history vs tokens.bin)', copy(lambda d: reseal(d,
        [(f'"token_history":[{h0},{h1}]', f'"token_history":[{h0},{h1x}]'), (f'{{"history0":{h0},"history1":{h1},"bank_parity"', f'{{"history0":{h0},"history1":{h1x},"bank_parity"')],
        [(f'history1\t{h1}\n', f'history1\t{h1x}\n'), (f'rank\t0\t{q0}\t{g0}\t{h0}\t{h1}\t', f'rank\t0\t{q0}\t{g0}\t{h0}\t{h1x}\t')])), 'token state')
    expect('rank1 draft position, resealed', copy(lambda d: reseal(d, [('"draft_position":%d' % (len(hist) - 1), '"draft_position":%d' % (len(hist) - 2))])), 'manifest')
    expect('tokens.bin altered', copy(lambda d: (d / 'tokens.bin').write_bytes(struct.pack('<i', 4) + (d / 'tokens.bin').read_bytes()[4:])), 'token state')
    expect('engine binary, resealed', copy(lambda d: reseal(d, [('"binary_sha256":"' + sha(ENGINE) + '"', '"binary_sha256":"' + '0' * 64 + '"')],
        [('binary_sha256\t' + sha(ENGINE), 'binary_sha256\t' + '0' * 64)])), 'engine identity', where='rank verify')
    expect('contract, resealed', copy(lambda d: reseal(d, [('"contract":"v1.2+p184"', '"contract":"v1.2+p181"')], [('contract\tv1.2+p184', 'contract\tv1.2+p181')])), 'manifest')
    expect('label, resealed', copy(lambda d: reseal(d, [('"label":"experimental-two-card"', '"label":"qualified-one-card"')], [('label\texperimental-two-card', 'label\tqualified-one-card')])), 'manifest')
    expect('append with a wrong pending token', copy(), 'prefix', inp=hist + [(pend + 1) % 16, 3], where='rank verify')
    expect('resume beyond the context', copy(), 'context', count=256, where='rank verify')
    other = W / 'tokenizer-other.tsv'
    other.write_text(TOK.read_text().replace('vocab_bin_sha256\t7a', 'vocab_bin_sha256\t7b', 1))
    with tokenizer(other):
        expect('tokenizer identity differs', copy(), 'tokenizer identity', where='rank verify')
    expect('coordinator lock not held (rank lock proof)', copy(), 'lock', hold_lock=False, where='rank verify')
    return rows


@contextlib.contextmanager
def tokenizer(path):
    global TOK
    old, TOK = TOK, path
    try:
        yield
    finally:
        TOK = old


def locks(root):
    rows = []
    _, base, _, _ = fresh('lock-base', root, PROMPT, 6, 'l-base')
    with T.Lock(root, 'l-base', False, 'restore'):          # a restore in progress (shared)
        code, row = T.tool(TOOL, '--checkpoint-delete', root / 'l-base')
        check(code == 1 and row['reason'] == 'in_use' and (root / 'l-base/manifest.json').exists(), 'delete during restore must report in_use')
        code, row = T.tool(TOOL, '--checkpoint-inspect', root / 'l-base')
        check(code == 0 and row['ok'], 'inspect shares the lock with a restore')
        rows.append('delete during restore -> in_use; inspect concurrent with restore -> ok')
    with T.Lock(root, 'l-base', True, 'save'):              # a save/delete in progress (exclusive)
        code, row = T.tool(TOOL, '--checkpoint-inspect-metadata', root / 'l-base')
        check(code == 1 and row['error']['check'] == 'lock', 'inspect during an exclusive holder must be refused')
        try:
            T.Lock(root, 'l-base', False, 'restore')
            raise AssertionError('shared lock granted during exclusive')
        except T.Refused as error:
            check(error.check == 'lock', 'restore during save must be refused (never waits)')
        rows.append('inspect and restore during save/delete -> refused (never wait)')
    plain = root / 'not-a-checkpoint'
    plain.mkdir()
    (plain / 'manifest.json').write_text('{}')
    code, row = T.tool(TOOL, '--checkpoint-delete', plain)
    check(code == 1 and row['reason'] == 'not_a_checkpoint' and plain.exists() and not (root / 'not-a-checkpoint.lock').exists(),
          'delete must validate its target before creating a lock')
    rows.append('delete of a non-checkpoint -> not_a_checkpoint, no lock file created')
    code, row = T.tool(TOOL, '--checkpoint-delete', root / 'l-base')
    check(code == 0 and row['deleted'] and not (root / 'l-base').exists() and not (root / 'l-base.lock').exists(), 'delete')
    rows.append('delete -> directory and lock removed')
    try:
        fresh('save-existing', root, PROMPT, 6, 'r-base')
        raise AssertionError('save over an existing checkpoint must be refused')
    except T.Refused as error:
        check(error.check == 'never overwrite', 'never overwrite')
    rows.append('save into an existing id -> never overwrite')
    # a failed stage leaves nothing visible (both ranks or none)
    real = T.write_tokens

    def poisoned(path, tokens):
        real(path, tokens)
        (Path(path).parent / 'rank1' / 'junk.bin').write_bytes(b'x')
    T.write_tokens = poisoned
    try:
        fresh('save-fails', root, PROMPT, 6, 'l-fail')
        raise AssertionError('rank 1 stage refusal expected')
    except AssertionError:
        raise
    except Exception:
        pass
    finally:
        T.write_tokens = real
    check(not (root / 'l-fail').exists(), 'a failed two-card save must leave no directory')
    rows.append('rank 1 stage failure -> no directory left (manifest never written)')
    record('locks and save atomicity', cases=len(rows))
    return rows


def main():
    limits()
    started = time.monotonic()
    shutil.rmtree(W, ignore_errors=True)
    (W / 'pairs').mkdir(parents=True)
    root = W / 'ckpt'
    root.mkdir()
    os.environ['OMP_NUM_THREADS'] = '2'
    for f in (ENGINE, TOOL):
        links = __import__('subprocess').run(['readelf', '-d', str(f)], capture_output=True, text=True, check=True).stdout.lower()
        check(not any(x in links for x in ('libsycl', 'libze_loader', 'libur_loader', 'libopencl')), 'host-only binary required: ' + str(f))
    result = dict(lifecycle=lifecycle(root), append=append(root), coverage=coverage(root), draft=draft_necessity(root),
                  refusals=refusals(root), locks=locks(root))
    pairs = len(list((W / 'pairs').iterdir()))
    save(HERE / 'evidence/checkpoint-cpu.json', dict(
        passed=True, device_executed=False, model_weights_read=False, scope='CPU mini geometry, real two-rank host engine; not a device result',
        engine_sha256=sha(ENGINE), tool_sha256=sha(TOOL), selection=str(SEL.relative_to(ROOT)), selection_sha256=sha(SEL),
        tokenizer_identity_sha256=sha(HERE / 'tokenizer-identity.tsv'), rank_pairs_launched=pairs, seconds=round(time.monotonic() - started, 1),
        cases=CASES, **result,
        sources={str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__).resolve(), HERE / 'tp2_checkpoint.py', SEL, HERE / 'tokenizer-identity.tsv')}))
    shutil.rmtree(W)
    print('checkpoint CPU gate PASS:', len(CASES), 'cases,', pairs, 'rank pairs,', round(time.monotonic() - started, 1), 's')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    main()

import copy
from oracle_fixture import load, run, pinned_rows

m = load()
frozen = pinned_rows(4)
frozen['rows'].reverse()
original = copy.deepcopy(frozen)
code, result, calls = run(m, pinned=frozen)
assert code == 0 and result is not None, 'PINNED_SUBSET: exact requested prompts must work with a larger frozen oracle'
assert frozen == original, 'Do not mutate the caller oracle'
assert len(calls) == 6, 'Pinned oracle use must not regenerate sequential outputs'
assert [r['prompt_id'] for r in result['oracle']['rows']] == ['a-c000','a-c001']
assert result['oracle']['request_count'] == 2
assert all(b['oracle_exact_all'] for b in result['batches'])
assert result['config']['oracle_digests_sha256']
code, equal, _ = run(m, pinned=pinned_rows(2))
assert code == 0 and equal['classification'] == 'output-identity-qualified'
invalids = []
missing = pinned_rows(1); invalids.append(missing)
changed = pinned_rows(4); changed['rows'][0]['prompt_sha256'] = '0'*64; invalids.append(changed)
duplicate = pinned_rows(4); duplicate['rows'].append(dict(duplicate['rows'][3])); invalids.append(duplicate)
nonstring = pinned_rows(4); nonstring['rows'][3]['prompt_id'] = 5; invalids.append(nonstring)
for document in invalids:
    code, invalid, calls = run(m, pinned=document)
    assert code != 0 and invalid is None and not calls, 'Invalid oracle must fail before any measured request'
print('PASS: reordered superset, equal set, preserved digest, missing/mismatched/duplicate/invalid identity refusal')

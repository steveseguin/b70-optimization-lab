from oracle_fixture import load, run

m = load()
code, result, first = run(m, ['--request-id-prefix', 'first lane / R7'])
assert code == 0 and result is not None, 'RUN_ID_ISOLATION: run-specific request identifiers must be accepted'
code, other, second = run(m, ['--request-id-prefix', 'second lane / R7'])
assert code == 0
assert len(first) == len(set(first)) == 8, 'Every oracle and measured request needs a unique identifier'
assert len(second) == len(set(second)) == 8
assert not set(first) & set(second), 'Different runs must not reuse request identifiers'
assert all(x.startswith('first-lane-R7-') for x in first)
assert all(x.startswith('second-lane-R7-') for x in second)
assert any('-oracle-' in x for x in first) and any('-c2-r2-' in x for x in first)
assert result['config']['request_id_prefix'] == 'first-lane-R7'
assert result['classification'] == other['classification'] == 'output-identity-qualified'
assert [b['request_count'] for b in result['batches']] == [1,2,1,2]
code, default, ids = run(m)
assert code == 0 and len(ids) == len(set(ids)) == 8
assert default['config']['request_id_prefix'] and all(
    x.startswith(default['config']['request_id_prefix'] + '-') for x in ids)
code, invalid, ids = run(m, ['--request-id-prefix', '///'])
assert code != 0 and invalid is None and not ids, 'Unsafe empty prefix must fail before requests'
print('PASS: distinct run namespaces, safe normalization, defaults and refusal before transport')

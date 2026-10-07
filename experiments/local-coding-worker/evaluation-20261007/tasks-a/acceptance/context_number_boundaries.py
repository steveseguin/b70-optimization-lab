import importlib.util
from pathlib import Path
p = Path.cwd() / 'experiments/qwen38-27b-b70/scripts/context/ctxfold.py'
s = importlib.util.spec_from_file_location('target_ctxfold', p)
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
cases = [
 ('Stock fell by eighty-three. Two packers checked it.', [83, 2]),
 ('Count was twenty-one; seven more were planned.', [21, 7]),
 ('aba12 has forty-two units and bcb34 has minus sixteen.', [42, -16]),
 ('One hundred and six arrived.', [106]),
 ('minus forty-two', [-42]),
 ('Three thousand two hundred and five.', [3205]),
 ('delta72: 17; omega31: -8', [17, -8]),
 ('eighty-three two', [83, 2]),
 ('ten, four: twelve! nine?', [10, 4, 12, 9]),
 ('The pallet has no numerical amount.', []),
]
for text, expected in cases:
 actual = m.numbers(text)
 assert actual == expected, f'NUMBER_BOUNDARY_FAILURE: {text!r}: expected {expected}, got {actual}'
print('PASS: narrative number boundaries, identifiers, compounds and signs')

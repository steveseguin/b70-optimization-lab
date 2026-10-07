"""Inactive, exact-source restriction of110 capture guard to six full outputs.

Reuse the existing prewrite/statistics/serialization contract. No fill/setup
outputs, role inference from caller labels, retry or refund are permitted.
This produces source bytes only; it does not register or install a runtime.
"""
import hashlib

SOURCE_SHA256 = '0f1b45631d87caf61e6d7b1396f9ddfd0fbdd66e719dd9df6abc9c2622c63036'


def transform_guard(raw):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Expected exact sealed110 capture guard')
    text = raw.decode()
    changes = (
        ('RAW_CAPTURE_BUDGET = 42 * FULL_FILE_BOUND + 8 * FILL_FILE_BOUND',
         'RAW_CAPTURE_BUDGET = 6 * FULL_FILE_BOUND'),
        ('WRITE_ALLOWANCE = 9 * 1024 ** 3', 'WRITE_ALLOWANCE = 4 * 1024 ** 3'),
        ('Bind50 capture rows', 'Bind6 full capture rows'),
        ('role counts are40 full,8 fill,2 setup; setup is charged as full and accepts\n'
         '    either an exact full tuple or an exact fill tuple.',
         'role counts are6 full,0 fill,0 setup; only complete full tuples are admitted.'),
        ("len(capture_rows) == 50, 'Exactly50 capture rows required'",
         "len(capture_rows) == 6, 'Exactly6 full capture rows required'"),
        ("len({r['name'] for r in capture_rows}) == 50", "len({r['name'] for r in capture_rows}) == 6"),
        ("{'full': 40, 'fill': 8, 'setup': 2}", "{'full': 6, 'fill': 0, 'setup': 0}"),
        ("'ltx.duration110-prewrite.v1'", "'ltx.continuation111-prewrite.v1'"),
        ("'capture_cap': 50", "'capture_cap': 6"),
    )
    for before, after in changes:
        if text.count(before) != 1:
            raise ValueError('Capture source anchor differs: ' + before)
        text = text.replace(before, after, 1)
    return text.encode()

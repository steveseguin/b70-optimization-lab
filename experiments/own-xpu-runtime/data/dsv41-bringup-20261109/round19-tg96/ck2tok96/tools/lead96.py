"""Segment A lead of the pace cards: from segs96.py output files, per step group, the work before arriving at the
output-a exchange on the pace cards (2, 5) and the light cards (0, 1, 3, 4), the lead (pace mean - light mean) in us
per step and per layer (40 layers), and the light cards' slack per layer (= the lead / 40).
usage: python3 -I lead96.py SEGS.txt [SEGS.txt ...]"""
import sys

for path in sys.argv[1:]:
    steps = None
    with open(path) as f:
        for line in f:
            if line.startswith('==='):
                print(line.strip())
            elif line.startswith('steps') and ' span ' in line:
                steps = line.split(' span')[0]
                span = line.split('span ')[1].split(' us')[0]
            elif line.startswith('A attn'):
                v = [float(x) for x in line.split('|')[-1].split()]
                pace = (v[2] + v[5]) / 2
                light = (v[0] + v[1] + v[3] + v[4]) / 4
                print('%-48s span %6s us | pace %6.0f light %6.0f | lead %4.0f us per step, %5.1f us per layer'
                      % ('%s: %s' % (path.rsplit('/', 1)[-1], steps), span, pace, light, pace - light,
                         (pace - light) / 40))

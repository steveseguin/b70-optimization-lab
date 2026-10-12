guess rate by prompt: incident-retrospective 54/64, code-review 43/64, customer-email 52/64, benchmark-analysis 49/64

| Case | first half / second half / draft (ms) | incident-retrospective | code-review | customer-email | benchmark-analysis | median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| packet 36 as measured: T=45.9, D=4.2, python controller | 22.8 / 23.1 / 4.2 | 32.8 | 29.1 | 31.8 | 31.2 | 31.5 |
|   + cancel a wrong half at once | 22.8 / 23.1 / 4.2 | 32.8 | 29.1 | 31.8 | 31.2 | 31.5 |
| packet 38 expected: T=41.4 (packet 37 halves), D=3.7, native controller | 20.7 / 20.7 / 3.7 | 36.8 | 32.7 | 35.7 | 35.0 | 35.3 |
|   + cancel a wrong half at once | 20.7 / 20.7 / 3.7 | 36.8 | 32.7 | 35.7 | 35.0 | 35.3 |
|   draft on rank 0, layers rebalanced (rank 0 half = rank 1 half - D) | 18.8 / 22.6 / 3.7 | 38.7 | 33.9 | 37.4 | 36.5 | 36.9 |
|   draft on rank 0, rebalanced, + cancel | 18.8 / 22.6 / 3.7 | 38.7 | 33.9 | 37.4 | 36.5 | 36.9 |
|   the same with a 2.5 ms draft | 19.4 / 21.9 / 2.5 | 39.4 | 34.4 | 38.0 | 37.1 | 37.6 |
|   the same with T=38 (epilogues, QSA attention) and a 2.5 ms draft | 17.8 / 20.2 / 2.5 | 42.8 | 37.3 | 41.2 | 40.3 | 40.8 |

# Shipped packet16 violations

Only never-written snapshot readbacks were reported on valid inputs. There is
no missing writer edge to name: the bytes have no writer at all. The fixes
initialize the slab; adding a dependency alone cannot repair this violation.

## Real model, two cards, resident

Each slab is 983040 bytes. Card0 has unwritten range [491520,983040);
card1 has unwritten range [0,491520). The run uses original prompt tokens at
positions0/1 and a generated-token input at position2. Captures follow positions1/2.

- `position=1:readback:card0:layer-snapshots:0: uninitialized read allocation=card0:layer-snapshots:0`
- `position=1:readback:card1:layer-snapshots:1: uninitialized read allocation=card1:layer-snapshots:1`
- `position=2:readback:card0:layer-snapshots:0: uninitialized read allocation=card0:layer-snapshots:0`
- `position=2:readback:card1:layer-snapshots:1: uninitialized read allocation=card1:layer-snapshots:1`

## Mini model

The full occurrence list for both card counts and seeds0,1,17,73 is retained
in mini-shipped-gates.json. Each run captures positions4,5,6. Card0 reports one
unwritten segment per capture; the two-card mini also reports two unwritten
segments on card1 per capture (unused layer slices around its owned slice).
The total is 3 reports per one-card run and 9 per two-card run, 48 reports across
8 runs. Repeated messages are separate poisoned ranges, not separate missing edges.

## No other shipped-path violations observed

No RAW, WAR, WAW, foreign binding, pending release or never-written index input
was reported on valid inputs. The checker negative tests deliberately create
these classes and must not be confused with findings in the shipped runtime.
The local index guard gaps are separately demonstrated malformed-input cases,
not a reproduced first-token fault. The native driver is not simulated.

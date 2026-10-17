# Packet49b decisions and negative-result index

| Finding | Evidence | Revisit condition |
| --- | --- | --- |
| SPEED6 is a historical identity, not current packet45 HEAD | Packet49 derives from `34c62b433`; packet49b from `5cda094d2` | New explicitly qualified baseline |
| Packet48 isolated dense timings are not production evidence | Packet48b production comparison | Fresh matched wrapper/shape evidence |
| GDN QKV/Z M=1 not worthwhile; M=2 production match absent | [Packet48b evidence](../packet48b-production/evidence-copy/p48b-a-summary.json) | Fresh production-matched M=2 byte and timing gates |
| Full16-byte expert row padding exceeds existing arena headroom | [Memory and load-alignment proof](INTEGRATION.md) | New separately qualified memory mechanism; never silently raise the cap |
| Exceptional IQ3 gate gain was about1% and closed for this merge | [Packet48b preregistration](../packet48b-production/PREREGISTRATION.md) | New worthwhile production-matched evidence |
| Four-row IQ4 down fixture fails the production geometry guard | `p49b-fixture-correction.json`, initial source `122d95fba` | Use2560 output rows, preserving the production guard |
| Split32 requires its own oracle, but expert arithmetic does not change it | [Shared packet49 binding](oracle-binding.json) | Any arithmetic change requires a separate identity |
| Ordered QSA alternative slower; packet46 layer launch fusion neutral | Packet49 inherited decisions | New mechanism with worthwhile gain estimate |
| M=2 bridge support does not mean batched engine scheduling | [Integration](INTEGRATION.md) | Separate scheduling change with rollback/quality gates |

The [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) records this task's
outcome and remaining gates. Device qualification and further optimization
remain open.

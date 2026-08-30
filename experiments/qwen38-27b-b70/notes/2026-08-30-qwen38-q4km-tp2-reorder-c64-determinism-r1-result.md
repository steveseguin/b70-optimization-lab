# Qwen3.8-27B Q4_K TP2 c64 reorder isolation

Disabling scoped Q4_K reorder did not restore sequential-to-c64 token
exactness. The fresh WDC-off/reorder-off diagnostic matched **36/64** outputs
and measured 165.608654 aggregate tok/s. The earlier reorder-on control matched
38/64 at 166.488675 tok/s. Both were complete, cache-zero, collision-free, and
free of kernel errors.

Therefore reorder is not the primary cause of the batch-shape output boundary.
The backend/model path is generally sensitive to batch shape. This is distinct
from run-to-run nondeterminism: the next gate freezes the reorder-on control's
c64 token outputs, replays them on a fresh c64 control, and requires WDC to
match that same-shape oracle on two fresh servers. The sequential-to-c64 caveat
remains explicit.

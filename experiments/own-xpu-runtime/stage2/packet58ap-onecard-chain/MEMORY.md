# Packet58ap memory and disk admission

The complete resident-parent allowance remains. Demand staging adds
129,302,528 bytes of host allowance, bringing the host bound to
90,529,619,968 bytes and available-RAM admission to 99,119,554,560 bytes
including 8 GiB reserve. `allocation-plan.json` retains the parent accounting.
The live sensor still counts all anonymous allocations and refuses more than
4 GiB unexplained GPU shadow. Nothing changes host settings or page cache.

The demand buffers fit within the inherited transfer device allowance;
the real CPU preparation allocation census is retained for every model
window. Native after-load/census checks and the fixed device reserve remain
mandatory on the coordinator's actual run. CPU sparse allocations are not
measured device memory or evidence of successful device allocation.

Device launch requires 25,000,000,000 free root bytes after reserved output
writes. The inherited seven-window write budget is 397,492,208 bytes; it
does not include detailed demand profiling, which is disabled. CPU children
peaked at 926,150,656 resident bytes in the first complete sequence, below
the 4 GB preparation budget. No weights or device files were opened.

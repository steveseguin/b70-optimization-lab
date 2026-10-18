def cooldown(now, sleep, until):
    sleep(
        min(.25, max(until - now(), 0))
    )

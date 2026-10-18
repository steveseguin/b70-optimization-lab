def cooldown(self, until):
    # This clamps the cap, not the actual remainder.
    self.sleep(min(max(0.0, .25), until - self.now()))

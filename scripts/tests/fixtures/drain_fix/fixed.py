def cooldown(self, until):
    while self.now() < until:
        self.check()
        self.sleep(max(0.0, min(.25, until - self.now())))

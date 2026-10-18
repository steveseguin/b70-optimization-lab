def cooldown(self, until):
    while self.now() < until:
        self.check()
        self.sleep(min(.25, until - self.now()))

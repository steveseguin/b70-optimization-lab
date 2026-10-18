def cooldown(self, until):
    self.sleep(max(0.0, min(.25, until - self.now())))
    self.sleep(min(.25, until - self.now()))

"""Keep shared v4 lifecycle; clamp its cooldown sleep as packet124b does."""
import time
from conditions import Teardown as SharedTeardown
class Teardown(SharedTeardown):
 def __init__(self,*args,**kwargs):
  sleep=kwargs.pop('sleep',time.sleep)
  super().__init__(*args,sleep=lambda delay:sleep(max(0.0,delay)),**kwargs)

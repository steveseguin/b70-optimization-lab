"""Packet124c's static authority plus its real read-only completion subprocess."""
import subprocess
from build131 import P

def verify_oracle():
 from shared_oracle import static_binding
 binding = static_binding()
 command = ['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P/'shared_oracle.py'),'--require-complete']
 result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                         text=True, timeout=180)
 if result.returncode:
  raise ValueError('complete shared oracle refused: ' + result.stderr[-2000:])
 return dict(binding=binding, command=command, returncode=result.returncode)

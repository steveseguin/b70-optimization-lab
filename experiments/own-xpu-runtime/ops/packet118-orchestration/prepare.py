"""Refresh packet118r CPU decision, chain binding and proposals; never execute."""
import json,subprocess,sys
from source_decision import O,ROOT,P,save

def main():
 for cmd in ([sys.executable,'-B',str(O/'source_decision.py')],):subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,check=True)
 subprocess.run([sys.executable,'-B',str(O/'policy_seal.py')],cwd=ROOT,stdin=subprocess.DEVNULL,check=True)
 from prepare_combined import main as prepare_combined
 prepare_combined()
if __name__=='__main__':main()

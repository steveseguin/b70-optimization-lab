"""Verify the retained composed source/build closure; never recopy parents."""
from source_decision import P
import sys
sys.path.insert(0,str(P))
from reuse_build import verify_native
if __name__=='__main__':verify_native();print('Composed build source identity PASS')

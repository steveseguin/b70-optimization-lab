"""Verify immutable views and reseal only the active packet75 chain."""
from prepare_selections import main as verify_views
from screen_seal_support import wrapper_seal
from fast_reseal import main
if __name__=='__main__':
    wrapper_seal();verify_views();main()

"""Use the owning packet proposal builder; never write a live queue."""
import runpy
from pathlib import Path
if __name__=="__main__":runpy.run_path(str(Path(__file__).resolve().parents[1]/"plan_queue.py"),run_name="__main__")

"""Launch the unchanged legacy application with the installed Python 2 interpreter."""
import os
import runpy
import sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(root, ".deps-py2"))
sys.path.insert(0, os.path.join(root, "py2"))
os.chdir(os.path.join(root, "py2"))
runpy.run_path("flaskServer.py", run_name="__main__")

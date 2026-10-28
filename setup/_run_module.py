"""Run a module as __main__ (used by doctor.py to start an MCP server over stdio)."""
import runpy
import sys

if __name__ == "__main__":
    mod = sys.argv[1]
    sys.argv = [mod] + sys.argv[2:]
    runpy.run_module(mod, run_name="__main__", alter_sys=True)

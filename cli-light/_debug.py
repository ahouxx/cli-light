"""Debug wrapper: run cli_light and capture any exceptions."""
import sys
import os
import traceback

# Write any errors to a temp log file
log_path = os.path.join(os.path.expanduser("~"), ".cli-light", "debug.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

try:
    sys.stderr = open(log_path, 'w')
    sys.stdout = open(log_path, 'a')
    print("=== Starting CLI Light ===", flush=True)
    from cli_light import CLILight
    app = CLILight()
    print(f"hook_port={app._hook_port}, root={app.root is not None}", flush=True)
    app.run()
except Exception:
    with open(log_path, 'a') as f:
        traceback.print_exc(file=f)
    # Also try to clean up any window
    try:
        import tkinter as tk
        for w in tk.Tk.winfo_children():
            pass
    except:
        pass

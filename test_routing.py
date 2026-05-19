#!/usr/bin/env python3
import sys
import traceback

try:
    print("Starting test...", flush=True)
    from network import Network
    from LSrouter import LSrouter
    
    print("Imports successful", flush=True)
    
    net = Network("01_small_net.json", LSrouter, visualize=False)
    print("Network created successfully", flush=True)
    
    net.run()
    print("Network run completed", flush=True)
    
except Exception as e:
    print(f"Error: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

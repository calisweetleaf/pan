"""
Compatibility shim: expose PAN_SDK.API as a module that loads the
existing `API.server.py` file (keeps your single-file layout working
while supporting standard imports like `import PAN_SDK.API`).
"""
from pathlib import Path
import importlib.util
import sys

_here = Path(__file__).resolve().parent
_server_file = _here / "API.server.py"

if _server_file.exists():
    spec = importlib.util.spec_from_file_location("PAN_SDK.API_server", str(_server_file))
    module = importlib.util.module_from_spec(spec)
    # Execute the module in its own namespace
    spec.loader.exec_module(module)  # type: ignore

    # Re-export common public names if present
    for name in ("SovereignAPIServer", "SovereignIdentity", "SovereignInferenceEngine", "ModelManifest"):
        if hasattr(module, name):
            globals()[name] = getattr(module, name)

    # Expose the module object for advanced use
    __server_module__ = module
    __all__ = [n for n in globals().keys() if not n.startswith("_")]
else:
    raise ImportError(f"PAN_SDK API server file not found at {_server_file}")

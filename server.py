"""CLI wrapper. The implementation lives in invisible_local_render/server.py."""

from pathlib import Path
import importlib.util

_path = Path(__file__).resolve().parent / "invisible_local_render" / "server.py"
_spec = importlib.util.spec_from_file_location("invisible_local_render_server", _path)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)

main = _module.main
get_buffer = _module.get_buffer
RESOLUTIONS = _module.RESOLUTIONS

if __name__ == "__main__":
    main()

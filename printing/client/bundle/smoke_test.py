"""Check the extracted Windows release without credentials or a printer."""

import ast
import importlib
from pathlib import Path
import subprocess
import sys


root = Path(sys.argv[1]).resolve()
assert Path(sys.executable).resolve() == root / "python" / "python.exe"
assert (root / ".env.sample").is_file()
assert (root / "run.bat").is_file()
assert not (root / ".env").exists(), "Never publish a configured credential file"

# Run the client's actual top-level imports, without executing its API calls.
source = root / "printer.py"
tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
exec(compile(ast.Module(body=imports, type_ignores=[]), str(source), "exec"))

# These native modules are imported only when a Windows job is printed.
for name in ("win32api", "win32print", "pywintypes", "google.protobuf", "grpc"):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(root), f"Dependency outside bundle: {name}: {path}"
    print(f"OK {name}: {path}")

assert (root / "vendor" / "gsprint" / "gsprint.exe").is_file()
ghostscript = root / "vendor" / "ghostscript" / "bin" / "gswin64c.exe"
subprocess.run(
    [str(ghostscript), "-dBATCH", "-dNOPAUSE", "-sDEVICE=nullpage", "-c", "showpage"],
    check=True,
)
print("PASS: extracted ZIP imports and Ghostscript rendering; no network or printer used")

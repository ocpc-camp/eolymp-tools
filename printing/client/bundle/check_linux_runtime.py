"""Check a relocated Linux bundle without API access or printing a page."""
import ast
import importlib
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
assert Path(sys.executable).resolve().is_relative_to(root / 'python')
assert sys.version_info >= (3, 12)
source = root / 'printer.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
exec(compile(ast.Module(body=imports, type_ignores=[]), str(source), 'exec'))
for name in ('eolymp', 'google.protobuf', 'grpc', 'requests', 'dotenv', 'ssl'):
    module = importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(root / 'python'), name
    print('OK', name)
for name in ('lp', 'lpstat', 'cancel'):
    assert shutil.which(name), f'Missing Ubuntu printing command: {name}'
print('PASS: portable Linux Python, all client imports, and CUPS commands')

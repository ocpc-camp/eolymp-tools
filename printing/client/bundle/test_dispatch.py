"""Exercise actual print dispatch without the live queue or a physical printer."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DispatchTest(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'printer.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('submit_and_confirm', '_job_id_from_lp')]
        self.run = Mock(return_value=SimpleNamespace(returncode=0, stdout='', stderr=''))
        self.env = dict(os=SimpleNamespace(name='nt'), subprocess=SimpleNamespace(run=self.run),
                        GSPRINT_PATH=r'C:\bundle (1)\vendor\gsprint\gsprint.exe',
                        GHOSTSCRIPT_PATH=r'C:\bundle (1)\vendor\ghostscript\bin\gswin64.exe',
                        PHYSICAL_PRINTER_NAME='MF460 Series', PRINT_MEDIA='A4', re=re)
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), self.env)

    def test_windows_uses_bundled_gsprint_with_separate_arguments(self):
        filename = r'C:\bundle (1)\job.pdf'
        self.assertEqual(self.env['submit_and_confirm'](filename), ('submitted', None))
        self.run.assert_called_once_with(
            [self.env['GSPRINT_PATH'], '-ghostscript', self.env['GHOSTSCRIPT_PATH'],
             '-printer', 'MF460 Series', filename], capture_output=True, text=True)

    def test_windows_failure_is_not_success(self):
        self.run.return_value.returncode = 1
        self.assertEqual(self.env['submit_and_confirm']('job.pdf'), ('error', None))

    def test_windows_missing_executable_is_not_success(self):
        self.run.side_effect = FileNotFoundError('missing gsprint')
        self.assertEqual(self.env['submit_and_confirm']('job.pdf'), ('error', None))

    def test_unix_retains_cups(self):
        self.env['os'].name = 'posix'
        self.assertEqual(self.env['submit_and_confirm']('job.pdf'), ('printed', None))
        self.run.assert_called_once_with(
            ['lp', '-d', 'MF460 Series', '-o', 'media=A4', 'job.pdf'],
            capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()

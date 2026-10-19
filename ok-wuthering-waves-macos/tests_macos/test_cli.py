import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from macos_port.cli import parser, read_settings
from macos_port.config import build_config


class CLITests(unittest.TestCase):
    def test_reject_invalid_timing_and_crop_before_native_imports(self):
        for args in [('run', '--duration', 'nan'), ('run', '--duration', '-1'),
                     ('capture', '--crop', '1,2,3'), ('capture', '--crop', '-1,0,0,0')]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser().parse_args(args)

    def test_settings_schema_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'tasks': {'FarmEchoTask': {'Repeat Farm Count': 1}}}))
            tasks, globals_ = read_settings(path)
            self.assertEqual(tasks['FarmEchoTask']['Repeat Farm Count'], 1)
            self.assertEqual(globals_, {})
            path.write_text('{"task": {}}')
            with self.assertRaises(ValueError): read_settings(path)

    def test_languages_match_upstream_task_support(self):
        en = build_config('en_US')
        tw = build_config('zh_TW')
        cn = build_config('zh_CN')
        names = lambda config: {name for _, name in config['onetime_tasks']}
        self.assertNotIn('ChangeEchoTask', names(en))
        self.assertNotIn('EnhanceEchoTask', names(en))
        self.assertIn('EnhanceEchoTask', names(tw))
        self.assertNotIn('ChangeEchoTask', names(tw))
        self.assertIn('ChangeEchoTask', names(cn))
        self.assertFalse(cn['ocr']['params']['use_openvino'])
        self.assertNotIn('windows', cn)


if __name__ == '__main__': unittest.main()

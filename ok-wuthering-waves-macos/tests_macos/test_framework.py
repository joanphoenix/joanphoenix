"""Exercise the real upstream executor and image assets against a fake native device."""
import os
from pathlib import Path
import tempfile
import unittest

from macos_port.config import build_config
from macos_port.framework import Runtime, load_framework
from macos_port.backend import MacOSBackend
from test_backend import FakeNative

load_framework()
from ok import BaseTask, TriggerTask

ROOT = Path(__file__).resolve().parents[1]


class ProbeTask(BaseTask):
    def run(self):
        self.next_frame()
        self.send_key("w", down_time=0)
        self.click(640, 360)


class FailedTask(BaseTask):
    def run(self):
        raise ValueError("deliberate engine test failure")


class IdleTrigger(TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config['_enabled'] = True
        self.trigger_interval = 0.01
    def run(self):
        self.send_key("a", down_time=0)


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.previous = Path.cwd()
        os.chdir(ROOT)
        self.addCleanup(os.chdir, self.previous)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.native = FakeNative()
        self.backend = MacOSBackend(native=self.native, start_watchdog=False)
        self.backend.select_window()
        self.config = build_config()
        self.config['config_folder'] = self.tmp.name
        self.config['ocr'] = None

    def runtime(self, full=False):
        if not full:
            self.config['onetime_tasks'] = [[__name__, 'ProbeTask'], [__name__, 'FailedTask']]
            self.config['trigger_tasks'] = [[__name__, 'IdleTrigger']]
        runtime = Runtime(self.config, self.backend)
        self.addCleanup(runtime.close)
        return runtime

    def test_original_executor_runs_one_time_task_and_stops(self):
        runtime = self.runtime()
        runtime.run('ProbeTask', duration=3)
        self.assertIn(('key', 13, True, frozenset({'w'})), self.native.events)
        self.assertIn(('button', (-640, 210), 'left', True), self.native.events)
        self.assertFalse(any(event[:2] == ('key', 0) for event in self.native.events))
        self.assertTrue(self.backend.stopped)

    def test_task_failure_propagates_and_releases_device(self):
        runtime = self.runtime()
        with self.assertRaisesRegex(RuntimeError, 'deliberate engine test failure'):
            runtime.run('FailedTask', duration=3)
        self.assertTrue(self.backend.stopped)

    def test_trigger_is_enabled_only_explicitly_and_duration_stops(self):
        runtime = self.runtime()
        self.assertFalse(any(task.enabled for task in runtime.executor.get_all_tasks()))
        runtime.run(triggers=['IdleTrigger'], duration=1.2)
        self.assertTrue(any(event[:2] == ('key', 0) for event in self.native.events))
        self.assertTrue(self.backend.stopped)

    def test_full_game_tasks_initialize_and_templates_load(self):
        runtime = self.runtime(full=True)
        names = {item['class_name'] for item in runtime.list_tasks()}
        self.assertIn('DailyTask', names)
        self.assertIn('AutoCombatTask', names)
        self.assertNotIn('MultiAccountDailyTask', names)
        self.assertFalse(any(task.enabled for task in runtime.executor.get_all_tasks()))
        feature_set = runtime.executor.feature_set
        feature_set.check_size(self.backend.capture())
        self.assertTrue(feature_set.feature_exists('pick_up_f_hcenter_vcenter'))
        task = runtime.executor.get_task_by_class_name('AutoPickTask')
        self.assertEqual(task.game_lang, 'en_US')

    def test_settings_reject_unknown_task(self):
        with self.assertRaisesRegex(ValueError, 'Unknown task configuration'):
            Runtime(self.config, self.backend, task_config={'NotATask': {}})

    def test_original_auto_pick_checks_blank_frame_without_sending_input(self):
        runtime = self.runtime(full=True)
        runtime.run(triggers=['AutoPickTask'], duration=1.3)
        self.assertEqual(self.native.events, [])
        self.assertTrue(runtime.executor.feature_set.load_success)


if __name__ == '__main__': unittest.main()

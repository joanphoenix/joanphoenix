"""App-level Mac regressions using mocks; these do not exercise the game."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_source(relative_path):
    spec = importlib.util.spec_from_file_location('_app_portability_test', ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AppPortabilityTests(unittest.TestCase):
    def test_mac_one_time_startup_does_not_import_windows_framework(self):
        with patch.object(sys, 'platform', 'darwin'), patch.dict(
                sys.modules, {'ok': None, 'win32api': None,
                              'src.task.MouseResetTask': None}):
            module = load_source('src/task/WWOneTimeTask.py')
            task = SimpleNamespace(sleep=Mock())
            module.WWOneTimeTask.run(task)
        task.sleep.assert_called_once_with(0.5)

    def load_mac_combat(self):
        ok = ModuleType('ok')
        ok.Logger = SimpleNamespace(get_logger=lambda _: Mock())
        for name in ('find_boxes_by_name', 'calculate_color_percentage',
                     'find_color_rectangles', 'get_mask_in_color_range', 'is_pure_black'):
            setattr(ok, name, Mock())
        base = ModuleType('src.task.BaseWWTask')
        base.BaseWWTask = type('BaseWWTask', (), {})
        roccia = ModuleType('src.char.Roccia')
        roccia.Roccia = type('Roccia', (), {})
        with patch.object(sys, 'platform', 'darwin'), patch.dict(
                sys.modules, {'ok': ok, 'win32api': None,
                              'src.task.BaseWWTask': base, 'src.char.Roccia': roccia}):
            return load_source('src/combat/CombatCheck.py')

    @staticmethod
    def levitator_task():
        task = MagicMock()
        task.config = {'Check Levitator': True}
        task.key_config = {'Wheel Key': 'tab'}
        task.find_one.return_value = None
        task.has_char.return_value = False
        task.is_open_world_auto_combat.return_value = False
        task.in_team.return_value = (False,)
        task.wait_feature.side_effect = [SimpleNamespace(x=200, y=300), True]
        task.target_enemy.return_value = True
        return task

    def test_mac_levitator_uses_only_guarded_capture_pixel_movement(self):
        module = self.load_mac_combat()
        task = self.levitator_task()
        self.assertTrue(module.CombatCheck.ensure_levitator(task))
        task.move.assert_called_once_with(200, 300)
        task.executor.interaction.capture.get_abs_cords.assert_not_called()
        task.send_key_up.assert_called_once_with('tab')

    def test_mac_levitator_releases_wheel_key_when_movement_is_blocked(self):
        module = self.load_mac_combat()
        task = self.levitator_task()
        task.move.side_effect = RuntimeError('Game lost focus')
        with self.assertRaisesRegex(RuntimeError, 'Game lost focus'):
            module.CombatCheck.ensure_levitator(task)
        task.send_key_up.assert_called_once_with('tab')
        task.target_enemy.assert_not_called()

    def test_mac_folder_open_preserves_spaces_without_a_shell(self):
        module = load_source('src/platform_utils.py')
        folder = ROOT / 'screenshots with spaces'
        with patch.object(module.sys, 'platform', 'darwin'), \
                patch.object(module.subprocess, 'run') as run:
            module.open_folder(folder)
        run.assert_called_once_with(['/usr/bin/open', str(folder)], check=True)


if __name__ == '__main__':
    unittest.main()

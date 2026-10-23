import unittest
from unittest.mock import MagicMock

from src.task.DailyTask import DailyTask
from src.task.ForgeryTask import ForgeryTask
from src.task.TacetTask import TacetTask


class TestF2ChallengeSelection(unittest.TestCase):

    def test_forgery_task_config_and_types(self):
        task = ForgeryTask(MagicMock(), MagicMock())
        self.assertEqual(task.total_number, 20)
        self.assertEqual(task.default_config['Which Forgery Challenge to Farm'], 1)
        config_type = task.config_type['Which Forgery Challenge to Farm']
        self.assertEqual(config_type['type'], 'int')
        self.assertEqual(config_type['min'], 1)
        self.assertEqual(config_type['max'], 20)

    def test_forgery_bounds(self):
        task = ForgeryTask(MagicMock(), MagicMock())
        task.open_boss_book = MagicMock()
        task.info_set = MagicMock()
        with self.assertRaises(IndexError):
            task.teleport_into_domain(0)
        with self.assertRaises(IndexError):
            task.teleport_into_domain(21)

    def test_tacet_task_config_and_types(self):
        task = TacetTask(MagicMock(), MagicMock())
        self.assertEqual(task.total_number, 21)
        self.assertEqual(task.default_config['Which Tacet Suppression to Farm'], 1)
        config_type = task.config_type['Which Tacet Suppression to Farm']
        self.assertEqual(config_type['type'], 'int')
        self.assertEqual(config_type['min'], 1)
        self.assertEqual(config_type['max'], 21)

    def test_tacet_bounds(self):
        task = TacetTask(MagicMock(), MagicMock())
        task.info_set = MagicMock()
        with self.assertRaises(IndexError):
            task.teleport_to_tacet(-1)
        with self.assertRaises(IndexError):
            task.teleport_to_tacet(21)

    def test_daily_task_config_and_types(self):
        task = DailyTask(MagicMock(), MagicMock())
        self.assertEqual(task.default_config['Which Forgery Challenge to Farm'], 1)
        self.assertEqual(task.default_config['Which Tacet Suppression to Farm'], 1)
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['type'], 'int')
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['min'], 1)
        self.assertEqual(task.config_type['Which Forgery Challenge to Farm']['max'], 20)
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['type'], 'int')
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['min'], 1)
        self.assertEqual(task.config_type['Which Tacet Suppression to Farm']['max'], 21)

    def test_config_widgets_instantiation(self):
        import sys
        from PySide6.QtWidgets import QApplication
        from ok import og
        from ok.ui.qt.tasks.ConfigItemFactory import config_widget
        from ok.ui.qt.tasks.LabelAndSpinBox import LabelAndSpinBox

        app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
        og.app = app

        class MockConfig(dict):
            def get_default(self, k):
                return self.get(k)

        for task in (ForgeryTask(MagicMock(), MagicMock()),
                     TacetTask(MagicMock(), MagicMock()),
                     DailyTask(MagicMock(), MagicMock())):
            cfg = MockConfig(task.default_config)
            for k in task.default_config:
                w = config_widget(task.config_type, task.config_description, cfg, k, task.default_config[k], task)
                self.assertIsNotNone(w)
                if 'Which Forgery Challenge' in k or 'Which Tacet Suppression' in k:
                    self.assertIsInstance(w, LabelAndSpinBox)
                    w.spin_box.resize(180, 33)
                    self.assertGreaterEqual(w.spin_box.lineEdit().geometry().width(), 80)
                    self.assertEqual(w.spin_box.lineEdit().text(), str(task.default_config[k]))

    def test_spinbox_visibility_and_interaction_in_task_card(self):
        import sys, os, tempfile
        from PySide6.QtWidgets import QApplication, QMainWindow
        from ok import og
        from ok.ui.qt.tasks.TaskCard import TaskCard
        from ok.util.config import Config
        from ok.ui.qt.tasks.LabelAndSpinBox import LabelAndSpinBox

        app = QApplication.instance() or QApplication(sys.argv)
        og.app = app
        og.config = {}
        og.executor = MagicMock()
        og.executor.waiting_for_task.return_value = False
        og.executor.is_task_running.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            og.app_path = tmpdir
            configs_dir = os.path.join(tmpdir, 'configs')
            os.makedirs(configs_dir, exist_ok=True)

            win = QMainWindow()

            for task_cls, conf_name, key in [
                (ForgeryTask, 'forgery', 'Which Forgery Challenge to Farm'),
                (TacetTask, 'tacet', 'Which Tacet Suppression to Farm'),
            ]:
                task = task_cls(MagicMock(), MagicMock())
                task.config = Config(conf_name, task.default_config, configs_dir)
                card = TaskCard(task, True)
                win.setCentralWidget(card)
                win.show()
                card.setExpand(True)
                for _ in range(5):
                    app.processEvents()

                widget = card.config_widget_by_key[key]
                self.assertIsInstance(widget, LabelAndSpinBox)
                sb = widget.spin_box
                line_edit = sb.lineEdit()

                # Ensure lineEdit has full width and visible number
                self.assertGreaterEqual(line_edit.geometry().width(), 100)
                self.assertTrue(line_edit.isVisible())
                self.assertEqual(line_edit.text(), '1')

                # Ensure up button increments and text updates
                sb.upButton.click()
                app.processEvents()
                self.assertEqual(sb.value(), 2)
                self.assertEqual(line_edit.text(), '2')

                # Ensure keyboard typing updates value and text
                line_edit.clear()
                line_edit.insert('15')
                sb.interpretText()
                app.processEvents()
                self.assertEqual(sb.value(), 15)
                self.assertEqual(line_edit.text(), '15')
                self.assertGreaterEqual(line_edit.geometry().width(), 100)


if __name__ == '__main__':
    unittest.main()

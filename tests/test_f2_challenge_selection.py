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

    def test_tacet_task_config_and_types(self):
        task = TacetTask(MagicMock(), MagicMock())
        self.assertEqual(task.total_number, 21)
        self.assertEqual(task.default_config['Which Tacet Suppression to Farm'], 1)
        config_type = task.config_type['Which Tacet Suppression to Farm']
        self.assertEqual(config_type['type'], 'int')
        self.assertEqual(config_type['min'], 1)
        self.assertEqual(config_type['max'], 21)

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


if __name__ == '__main__':
    unittest.main()

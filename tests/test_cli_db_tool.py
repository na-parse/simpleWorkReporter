import io
import unittest
from unittest.mock import patch

from simpleworkreporter.cli import db_tool


class DbtoolDemoConfirmTests(unittest.TestCase):
    def test_demo_clear_cancel_does_not_seed(self) -> None:
        with (
            patch('builtins.input', return_value='no'),
            patch('simpleworkreporter.cli.db_tool.seed_demo_tasks') as seed_demo_tasks,
            patch('sys.stdout', new_callable=io.StringIO),
        ):
            result = db_tool.demo(['--clear'])

        self.assertEqual(1, result)
        seed_demo_tasks.assert_not_called()

    def test_demo_clear_yes_bypasses_prompt(self) -> None:
        with (
            patch('builtins.input') as input_prompt,
            patch('simpleworkreporter.cli.db_tool.seed_demo_tasks', return_value=12) as seed_demo_tasks,
            patch('sys.stdout', new_callable=io.StringIO),
        ):
            result = db_tool.demo(['--clear', '-y'])

        self.assertEqual(0, result)
        input_prompt.assert_not_called()
        seed_demo_tasks.assert_called_once_with(clear=True)

    def test_demo_clear_eof_cancels(self) -> None:
        with (
            patch('builtins.input', side_effect=EOFError),
            patch('simpleworkreporter.cli.db_tool.seed_demo_tasks') as seed_demo_tasks,
            patch('sys.stdout', new_callable=io.StringIO),
        ):
            result = db_tool.demo(['--clear'])

        self.assertEqual(1, result)
        seed_demo_tasks.assert_not_called()


if __name__ == '__main__':
    unittest.main()

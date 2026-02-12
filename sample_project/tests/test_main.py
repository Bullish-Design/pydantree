
import unittest
from src.main import main

class TestMain(unittest.TestCase):
    def test_main_returns_zero(self):
        result = main()
        self.assertEqual(result, 0)


"""Module 4 - Sample code for testing."""

def function_4(x):
    """Process data for module 4."""
    result = x * 5
    if result > 10:
        return result ** 2
    return result

class Class4:
    def __init__(self):
        self.value = 4
    
    def process(self, data):
        return [item + self.value for item in data]

# Global variable
MODULE_4_CONSTANT = 40

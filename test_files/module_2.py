
"""Module 2 - Sample code for testing."""

def function_2(x):
    """Process data for module 2."""
    result = x * 3
    if result > 10:
        return result ** 2
    return result

class Class2:
    def __init__(self):
        self.value = 2
    
    def process(self, data):
        return [item + self.value for item in data]

# Global variable
MODULE_2_CONSTANT = 20

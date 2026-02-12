
"""Module 1 - Sample code for testing."""

def function_1(x):
    """Process data for module 1."""
    result = x * 2
    if result > 10:
        return result ** 2
    return result

class Class1:
    def __init__(self):
        self.value = 1
    
    def process(self, data):
        return [item + self.value for item in data]

# Global variable
MODULE_1_CONSTANT = 10


"""Module 3 - Sample code for testing."""

def function_3(x):
    """Process data for module 3."""
    result = x * 4
    if result > 10:
        return result ** 2
    return result

class Class3:
    def __init__(self):
        self.value = 3
    
    def process(self, data):
        return [item + self.value for item in data]

# Global variable
MODULE_3_CONSTANT = 30

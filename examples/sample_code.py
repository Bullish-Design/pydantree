#!/usr/bin/env python3
"""Sample Python code for pydantree testing."""

import math
from typing import List

class Calculator:
    """Simple calculator class."""
    
    def __init__(self, precision: int = 2):
        self.precision = precision
    
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        return round(result, self.precision)
    
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return round(a * b, self.precision)

def fibonacci(n: int) -> List[int]:
    """Generate fibonacci sequence."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

def main():
    """Main function."""
    calc = Calculator()
    print(f"2 + 3 = {calc.add(2, 3)}")
    print(f"Fibonacci(10): {fibonacci(10)}")

if __name__ == "__main__":
    main()

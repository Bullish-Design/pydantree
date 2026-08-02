import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tasks import Assignment, Person, PY_SAMPLE, JSON_SAMPLE
import tree_sitter_python, tree_sitter_json

print("=== Assignment: derived .scm ===")
print(Assignment.compiled_source())
Assignment.validate_with(tree_sitter_python)
print("\n=== Assignment.extract ===")
for a in Assignment.extract(PY_SAMPLE, language=tree_sitter_python):
    print(" ", a)

print("\n=== Person: derived .scm ===")
print(Person.compiled_source())
Person.validate_with(tree_sitter_json)
print("\n=== Person.extract ===")
for p in Person.extract(JSON_SAMPLE, language=tree_sitter_json):
    print(" ", p)

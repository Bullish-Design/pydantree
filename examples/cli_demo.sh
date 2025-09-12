#!/bin/bash
# CLI Usage Examples

echo "=== Pydantree CLI Demo ==="

# 1. Generate node types (requires node-types.json)
echo "1. Generate typed nodes:"
echo "python -m pydantree.cli generate src/data/node-types.json --out generated_nodes.py"

# 2. Show AST for sample file
echo -e "\n2. Display AST:"
echo "python -m pydantree.cli ast examples/sample.py --depth 3"

# 3. Query nodes
echo -e "\n3. Query functions:"
echo "python -m pydantree.cli query examples/sample.py --type function_definition"

# 4. Query with text filter
echo -e "\n4. Query with text filter:"
echo "python -m pydantree.cli query examples/sample.py --text 'fibonacci'"

# 5. Transform code
echo -e "\n5. Transform print statements:"
echo "python -m pydantree.cli transform examples/sample.py --transform print_to_logger"

# 6. Graph analysis (requires rustworkx)
echo -e "\n6. Graph analysis:"
echo "python -m pydantree.cli graph examples/sample.py --format stats"

# 7. Inline code examples
echo -e "\n7. Parse inline code:"
echo 'python -m pydantree.cli ast --code "def hello(): return \"world\""'

echo -e "\n8. Query inline code:"
echo 'python -m pydantree.cli query --code "x = 1 + 2" --type binary_operator'

echo -e "\nRun any of these commands to test pydantree functionality!"

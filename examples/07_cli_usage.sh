# examples/07_cli_usage.sh

# CLI Usage Examples for Pydantree

# ===============================================
# Basic CLI Commands
# ===============================================

# 1. Get help and version information
pydantree --version
pydantree --help
pydantree analyze --help

# 2. Analyze a single Python file
pydantree analyze script.py

# 3. Analyze with specific output format
pydantree analyze script.py --format table
pydantree analyze script.py --format json
pydantree analyze script.py --format csv

# 4. Save analysis results to file
pydantree analyze script.py --output results.json --format json

# ===============================================
# Directory Analysis
# ===============================================

# 5. Analyze entire directory
pydantree analyze src/ --recursive

# 6. Analyze with language specification
pydantree analyze src/ --language python --recursive

# 7. Limit number of files processed
pydantree analyze src/ --max-files 100 --recursive

# 8. Include error files in output
pydantree analyze src/ --include-errors --recursive

# 9. Parallel processing with custom workers
pydantree analyze src/ --workers 8 --recursive

# ===============================================
# Metrics and Analysis Options
# ===============================================

# 10. Different metric types
pydantree analyze src/ --metrics basic
pydantree analyze src/ --metrics advanced  
pydantree analyze src/ --metrics complexity
pydantree analyze src/ --metrics all

# 11. Exclude specific patterns
pydantree analyze src/ --exclude "test_*,*_test.py,__pycache__"

# 12. Verbose output with progress
pydantree analyze src/ --verbose --progress

# 13. Quiet mode (minimal output)
pydantree analyze src/ --quiet --output results.csv

# ===============================================
# AST Display Commands
# ===============================================

# 14. Display AST structure
pydantree ast script.py

# 15. Limit tree depth
pydantree ast script.py --depth 3

# 16. Hide text content
pydantree ast script.py --no-text

# 17. Show computed metrics in AST
pydantree ast script.py --metrics

# 18. Different output formats for AST
pydantree ast script.py --format tree
pydantree ast script.py --format json
pydantree ast script.py --format sexp

# 19. Save AST to file
pydantree ast script.py --output ast_structure.json --format json

# 20. Parse inline code
pydantree ast --code "def hello(): return 'world'" --language python

# ===============================================
# Batch Processing Commands
# ===============================================

# 21. Discover files in directory
pydantree batch discover src/

# 22. Discover with language filter
pydantree batch discover src/ --language python

# 23. Show detailed file information
pydantree batch discover src/ --details

# 24. Save file list
pydantree batch discover src/ --output filelist.txt

# 25. Basic batch processing
pydantree batch process src/ --output batch_results.jsonl

# 26. Batch processing with different modes
pydantree batch process src/ --mode sequential
pydantree batch process src/ --mode threaded --workers 4
pydantree batch process src/ --mode process --workers 2
pydantree batch process src/ --mode hybrid

# 27. Batch processing with compression
pydantree batch process src/ --compression gzip --output results.jsonl.gz
pydantree batch process src/ --compression lz4 --output results.jsonl.lz4

# 28. Streaming batch processing
pydantree batch process src/ --streaming --chunk-size 500

# 29. Export format options
pydantree batch process src/ --export full --format json
pydantree batch process src/ --export metrics --format csv
pydantree batch process src/ --export minimal --format binary

# ===============================================
# Performance and Profiling
# ===============================================

# 30. Enable performance profiling
pydantree analyze src/ --profile

# 31. Save performance profile
pydantree analyze src/ --profile --save-profile perf_report.json

# 32. Compare against baseline
pydantree analyze src/ --profile --baseline previous_perf.json

# 33. Dry run (show what would be processed)
pydantree batch process src/ --dry-run

# ===============================================
# Advanced Usage Examples
# ===============================================

# 34. Multi-language project analysis
pydantree analyze project/ --recursive --workers 6 \
  --output analysis.json --format json --verbose

# 35. Large codebase batch processing
pydantree batch process large_project/ \
  --mode hybrid --workers 8 --batch-size 200 \
  --compression zstd --streaming --chunk-size 1000 \
  --output large_analysis.jsonl.zstd

# 36. Quality analysis with metrics
pydantree analyze src/ --metrics all --include-errors \
  --output quality_report.csv --format csv

# 37. AST export for visualization
pydantree ast complex_module.py --format json --metrics \
  --output ast_for_viz.json

# 38. Performance benchmarking
pydantree batch process test_suite/ --mode threaded --workers 1 \
  --profile --save-profile single_thread.json

pydantree batch process test_suite/ --mode threaded --workers 4 \
  --profile --save-profile multi_thread.json

# ===============================================
# Code Generation Commands
# ===============================================

# 39. Generate typed node classes from grammar
pydantree generate node-types.json --out generated_nodes.py

# 40. Generate with custom options
pydantree generate node-types.json --out python_nodes.py \
  --language python --token-suffix Node --base-class TSNode

# 41. Generate with metadata and formatting
pydantree generate node-types.json --out formatted_nodes.py \
  --metadata --format

# ===============================================
# Practical Workflow Examples
# ===============================================

# 42. Complete project analysis workflow
#!/bin/bash

PROJECT_DIR="my_python_project"
OUTPUT_DIR="pydantree_analysis"

# Create output directory
mkdir -p $OUTPUT_DIR

# 1. Discover all source files
echo "Discovering source files..."
pydantree batch discover $PROJECT_DIR --details \
  --output $OUTPUT_DIR/source_files.txt

# 2. Analyze code quality
echo "Analyzing code quality..."
pydantree analyze $PROJECT_DIR --recursive --metrics all \
  --output $OUTPUT_DIR/quality_metrics.csv --format csv

# 3. Generate detailed AST analysis
echo "Processing ASTs..."
pydantree batch process $PROJECT_DIR \
  --export full --format jsonl --compression lz4 \
  --output $OUTPUT_DIR/ast_data.jsonl.lz4

# 4. Performance profiling
echo "Performance analysis..."
pydantree analyze $PROJECT_DIR --recursive --profile \
  --save-profile $OUTPUT_DIR/performance.json

echo "Analysis complete. Results in $OUTPUT_DIR/"

# 43. Continuous integration example
#!/bin/bash

# CI script for code quality checks
set -e

echo "Running Pydantree analysis..."

# Analyze changed files only (example with git)
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD -- "*.py")

if [ -n "$CHANGED_FILES" ]; then
    echo "Analyzing changed Python files:"
    echo "$CHANGED_FILES"
    
    # Create temporary file list
    echo "$CHANGED_FILES" > changed_files.txt
    
    # Analyze only changed files
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            pydantree analyze "$file" --metrics complexity --format json \
              --output "analysis_$(basename $file .py).json"
        fi
    done < changed_files.txt
    
    # Combine results
    pydantree batch process . --max-files 50 \
      --export metrics --format csv \
      --output ci_analysis_results.csv
    
    echo "Analysis complete. Check ci_analysis_results.csv"
else
    echo "No Python files changed."
fi

# 44. Development workflow helper
#!/bin/bash

# Helper script for developers
function analyze_file() {
    local file=$1
    echo "Analyzing $file..."
    
    # Quick analysis
    pydantree analyze "$file" --metrics basic --format table
    
    # Show AST structure
    echo -e "\nAST Structure (depth 2):"
    pydantree ast "$file" --depth 2 --no-text
    
    # Complexity check
    echo -e "\nComplexity Analysis:"
    pydantree analyze "$file" --metrics complexity --format json | \
      jq '.functions[] | select(.complexity > 10) | {name: .name, complexity: .complexity}'
}

# Use: analyze_file my_script.py

# 45. Batch comparison script
#!/bin/bash

# Compare analysis between two versions
VERSION1_DIR="version_1"
VERSION2_DIR="version_2"

echo "Comparing $VERSION1_DIR vs $VERSION2_DIR"

# Analyze both versions
pydantree analyze $VERSION1_DIR --recursive --metrics all \
  --output v1_metrics.json --format json

pydantree analyze $VERSION2_DIR --recursive --metrics all \
  --output v2_metrics.json --format json

echo "Analysis complete. Compare v1_metrics.json and v2_metrics.json"

# 46. Large repository analysis
#!/bin/bash

# For very large repositories
REPO_DIR="large_repository"
OUTPUT_DIR="analysis_output"

mkdir -p $OUTPUT_DIR

# Process in chunks to avoid memory issues
pydantree batch process $REPO_DIR \
  --mode hybrid --workers 6 --batch-size 100 \
  --streaming --chunk-size 50 \
  --compression zstd \
  --export minimal \
  --output $OUTPUT_DIR/large_repo_analysis.jsonl.zstd

# Generate summary statistics
pydantree analyze $REPO_DIR --recursive --metrics basic \
  --max-files 1000 \
  --output $OUTPUT_DIR/summary_stats.csv --format csv

echo "Large repository analysis complete."

#!/usr/bin/env bash
# real_script.sh — a REAL shell script from a sibling real project:
# an excerpt of llama-infernal's build-xcframework.sh (Bullish-Design/
# llama-infernal, MIT — the ggml authors). Verbatim lines: the options
# block, the check_required_tool() function, and the module.modulemap
# heredoc. It covers all three extraction tasks with genuine production
# bash (19 top-level options + version captures, 1 function, 1 heredoc).
#
# Options
IOS_MIN_OS_VERSION=16.4
MACOS_MIN_OS_VERSION=13.3
VISIONOS_MIN_OS_VERSION=1.0
TVOS_MIN_OS_VERSION=16.4

BUILD_SHARED_LIBS=OFF
LLAMA_BUILD_APP=OFF
LLAMA_BUILD_COMMON=OFF
LLAMA_BUILD_EXAMPLES=OFF
LLAMA_BUILD_TOOLS=OFF
LLAMA_BUILD_TESTS=OFF
LLAMA_BUILD_SERVER=OFF
LLAMA_BUILD_MTMD=ON
GGML_METAL=ON
GGML_METAL_EMBED_LIBRARY=ON
GGML_BLAS_DEFAULT=ON
GGML_METAL_USE_BF16=ON

check_required_tool() {
    local tool=$1
    local install_message=$2

    if ! command -v $tool &> /dev/null; then
        echo "Error: $tool is required but not found."
        echo "$install_message"
        exit 1
    fi
}

XCODE_VERSION=$(xcrun xcodebuild -version 2>/dev/null | head -n1 | awk '{ print $2 }')
MAJOR_VERSION=$(echo $XCODE_VERSION | cut -d. -f1)
MINOR_VERSION=$(echo $XCODE_VERSION | cut -d. -f2)

# Create module map (common for all platforms)
cat > ${module_path}module.modulemap << EOF
framework module llama {
    umbrella "Headers"

    link "c++"
    link framework "Accelerate"
    link framework "Metal"
    link framework "Foundation"

    export *
}
EOF

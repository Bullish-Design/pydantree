{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.uv
    pkgs.zellij
  ];

  scripts.project17-pytest-zellij.exec = ''
    set -euo pipefail
    session="project17-pytest-$(date -u +%Y%m%dT%H%M%SZ)"
    artifact_dir="$PWD/artifacts/$session"
    mkdir -p "$artifact_dir"
    zellij attach "$session" --create-background
    ZELLIJ_SESSION_NAME="$session" zellij run --name pytest --close-on-exit --cwd "$PWD" -- \
      ${pkgs.bash}/bin/bash -lc "pytest -o addopts='-ra' > '$artifact_dir/stdout-stderr.log' 2>&1; status=\$?; printf '%s\\n' \"\$status\" > '$artifact_dir/exit-status.txt'; exit \$status"
    echo "pytest is running in: zellij attach $session"
    echo "artifacts: $artifact_dir"
  '';

  scripts.project17-json-workload-zellij.exec = ''
    set -euo pipefail
    : "''${PROJECT17_MODEL:?set PROJECT17_MODEL to the Ornith GGUF path}"
    project17_corpus="''${PROJECT17_CORPUS:-benchmarks/project17/json_workload_100.jsonl}"
    project17_requests="''${PROJECT17_REQUESTS:-100}"
    project17_mode="''${PROJECT17_MODE:-constrained}"
    project17_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    project17_session="project17-json-$project17_stamp"
    project17_artifacts="$PWD/artifacts/project17-json-$project17_mode-$project17_stamp"
    project17_lib="''${PROJECT17_LIB_PATH:-$PWD/.devenv/state/venv/lib/python3.13/site-packages/llama_cpp/lib}"
    project17_cuda_ld="$(tr -d '\n' < "$PWD/.scratch/projects/17-llama-cpp-inference-lab/.cuda_runtime_ld")"
    mkdir -p "$project17_artifacts"
    {
      printf 'session=%s\n' "$project17_session"
      printf 'started_at_utc=%s\n' "$project17_stamp"
      printf 'mode=%s\ncorpus=%s\nrequests=%s\nmodel=%s\n' "$project17_mode" "$project17_corpus" "$project17_requests" "$PROJECT17_MODEL"
      printf 'llama_cpp_lib_path=%s\n' "$project17_lib"
      printf 'cuda_visible_devices=0\nn_gpu_layers=-1\n'
    } > "$project17_artifacts/run-config.txt"
    git status --short > "$project17_artifacts/git-status-before.txt"
    nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,memory.used --format=csv,noheader > "$project17_artifacts/gpu-before.csv"
    nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader > "$project17_artifacts/gpu-processes-before.csv" || true
    ps -eo pid,ppid,stat,args > "$project17_artifacts/processes-before.txt"
    zellij attach "$project17_session" --create-background
    ZELLIJ_SESSION_NAME="$project17_session" zellij run --name project17-json --close-on-exit --cwd "$PWD" -- \
      ${pkgs.bash}/bin/bash -lc '
        set -euo pipefail
        out="$1"; mode="$2"; corpus="$3"; requests="$4"; model="$5"; lib="$6"; cuda_ld="$7"; root="$8"
        cd "$root"
        baseline=""
        same=""
        case "$mode" in
          constrained) ;;
          baseline) baseline="--baseline-only" ;;
          same-grammar-repeated) same="--same-grammar-repeated" ;;
          *) printf "unknown PROJECT17_MODE: %s\\n" "$mode" >&2; exit 2 ;;
        esac
        export CUDA_VISIBLE_DEVICES=0
        export LLAMA_CPP_LIB_PATH="$lib"
        export LD_LIBRARY_PATH="$cuda_ld''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export PYTHONPATH="src:.devenv/state/venv/lib/python3.13/site-packages''${PYTHONPATH:+:$PYTHONPATH}"
        printf "CUDA_VISIBLE_DEVICES=%s\\nLLAMA_CPP_LIB_PATH=%s\\nLD_LIBRARY_PATH=%s\\nPYTHONPATH=%s\\n" "$CUDA_VISIBLE_DEVICES" "$LLAMA_CPP_LIB_PATH" "$LD_LIBRARY_PATH" "$PYTHONPATH" > "$out/runtime-environment.txt"
        printf "%q " .devenv/state/venv/bin/python benchmarks/project17/run_json_workload.py --model "$model" --corpus "$corpus" --requests "$requests" --artifacts "$out" $baseline $same > "$out/command.txt"
        printf "\\n" >> "$out/command.txt"
        ( while :; do date -u +%FT%TZ; nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader; sleep 15; done ) > "$out/gpu-during.csv" 2>&1 &
        monitor=$!
        trap "kill $monitor 2>/dev/null || true" EXIT
        set +e
        .devenv/state/venv/bin/python benchmarks/project17/run_json_workload.py --model "$model" --corpus "$corpus" --requests "$requests" --artifacts "$out" $baseline $same > "$out/stdout-stderr.log" 2>&1
        rc=$?
        set -e
        printf "%s\\n" "$rc" > "$out/exit-status.txt"
        nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,memory.used --format=csv,noheader > "$out/gpu-after.csv" || true
        nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader > "$out/gpu-processes-after.csv" || true
        ps -eo pid,ppid,stat,args > "$out/processes-after.txt"
        exit "$rc"
      ' -- "$project17_artifacts" "$project17_mode" "$project17_corpus" "$project17_requests" "$PROJECT17_MODEL" "$project17_lib" "$project17_cuda_ld" "$PWD"
    printf 'Project 17 benchmark running in Zellij: zellij attach %s\n' "$project17_session"
    printf 'Artifacts: %s\n' "$project17_artifacts"
  '';

  scripts.project17-prefix-cache-zellij.exec = ''
    set -euo pipefail
    : "''${PROJECT17_MODEL:?set PROJECT17_MODEL to the Ornith GGUF path}"
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    session="project17-prefix-cache-$stamp"
    out="$PWD/artifacts/project17-prefix-cache-$stamp"
    cache="$PWD/artifacts/project17-prefix-cache-store-$stamp"
    lib="''${PROJECT17_LIB_PATH:-$PWD/.devenv/state/venv/lib/python3.13/site-packages/llama_cpp/lib}"
    cuda_ld="$(tr -d '\n' < "$PWD/.scratch/projects/17-llama-cpp-inference-lab/.cuda_runtime_ld")"
    mkdir -p "$out" "$cache"
    git status --short > "$out/git-status-before.txt"
    nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,memory.used --format=csv,noheader > "$out/gpu-before.csv"
    ps -eo pid,ppid,stat,args > "$out/processes-before.txt"
    zellij attach "$session" --create-background
    ZELLIJ_SESSION_NAME="$session" zellij run --name project17-prefix-cache --close-on-exit --cwd "$PWD" -- \
      ${pkgs.bash}/bin/bash -lc '
        set -euo pipefail
        out="$1"; cache="$2"; model="$3"; lib="$4"; cuda_ld="$5"; root="$6"
        cd "$root"
        export CUDA_VISIBLE_DEVICES=0 LLAMA_CPP_LIB_PATH="$lib"
        export LD_LIBRARY_PATH="$cuda_ld''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export PYTHONPATH="src:.devenv/state/venv/lib/python3.13/site-packages''${PYTHONPATH:+:$PYTHONPATH}"
        env | rg "^(CUDA_VISIBLE_DEVICES|LLAMA_CPP_LIB_PATH|LD_LIBRARY_PATH|PYTHONPATH)=" > "$out/runtime-environment.txt"
        extra="''${PROJECT17_PREFIX_CACHE_ARGS:-}"
        printf "%q " .devenv/state/venv/bin/python benchmarks/project17/run_prefix_cache.py --model "$model" --artifacts "$out" --cache-root "$cache" $extra > "$out/command.txt"; printf "\n" >> "$out/command.txt"
        ( while :; do date -u +%FT%TZ; nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader; sleep 15; done ) > "$out/gpu-during.csv" 2>&1 & monitor=$!
        trap "kill $monitor 2>/dev/null || true" EXIT
        set +e
        .devenv/state/venv/bin/python benchmarks/project17/run_prefix_cache.py --model "$model" --artifacts "$out" --cache-root "$cache" $extra > "$out/stdout-stderr.log" 2>&1
        rc=$?
        set -e
        printf "%s\n" "$rc" > "$out/exit-status.txt"
        nvidia-smi --query-gpu=index,name,uuid,driver_version,memory.total,memory.used --format=csv,noheader > "$out/gpu-after.csv" || true
        ps -eo pid,ppid,stat,args > "$out/processes-after.txt"
        exit "$rc"
      ' -- "$out" "$cache" "$PROJECT17_MODEL" "$lib" "$cuda_ld" "$PWD"
    printf 'Project 17 prefix-cache run: zellij attach %s\nArtifacts: %s\n' "$session" "$out"
  '';

  # Foreground entrypoint for the GPU-gated pytest suite. Exports the proven
  # CUDA/llama.cpp runtime env, then runs pytest under the reference
  # interpreter (the devenv venv, which after the step-7 refactor carries the
  # llama-cpp-python binding + inferference). LLAMA_CPP_LIB_PATH defaults to the
  # Mode A wheel's bundled lib dir (the ABI-anchor unit inside this repo); set
  # PROJECT17_LIB_PATH to the Mode B out-p2fork-24c5d3dbc lib for nan-fix
  # iteration. Extra args pass through to pytest, e.g.
  #   project17-gpu-pytest -k reconstruct
  # Overridable: PROJECT17_MODEL, PROJECT17_CUDA_DEVICES (default 0),
  # PROJECT17_LIB_PATH, PROJECT17_SPIKE_PY (selects the reference interpreter;
  # default .devenv/state/venv/bin/python).
  scripts.project17-gpu-pytest.exec = ''
    set -euo pipefail
    root="$PWD"
    spike="$root/.scratch/projects/17-llama-cpp-inference-lab"
    py="''${PROJECT17_SPIKE_PY:-$PWD/.devenv/state/venv/bin/python}"
    model="''${PROJECT17_MODEL:-/home/nixuser/.cache/structured-agents/models/Ornith-1.0-9B-UD-Q4_K_XL.gguf}"
    lib="''${PROJECT17_LIB_PATH:-$PWD/.devenv/state/venv/lib/python3.13/site-packages/llama_cpp/lib}"
    cuda_ld="$(tr -d '\n' < "$spike/.cuda_runtime_ld")"
    if [ ! -x "$py" ]; then echo "reference python not found: $py (set PROJECT17_SPIKE_PY)" >&2; exit 2; fi
    if [ ! -f "$model" ]; then echo "model not found: $model (set PROJECT17_MODEL)" >&2; exit 2; fi
    if [ ! -d "$lib" ]; then echo "llama.cpp lib dir not found: $lib" >&2; exit 2; fi
    export CUDA_VISIBLE_DEVICES="''${PROJECT17_CUDA_DEVICES:-0}"
    export LLAMA_CPP_LIB_PATH="$lib"
    export LLAMA_TEST_MODEL="$model"
    # /run/opengl-driver/lib first so the real libcuda wins over any CUDA stub;
    # cuda_ld carries gcc-lib (libstdc++) + cudart/cublas the bindings dlopen.
    export LD_LIBRARY_PATH="/run/opengl-driver/lib:$lib:$cuda_ld''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PYTHONPATH="src''${PYTHONPATH:+:$PYTHONPATH}"
    printf 'python=%s\nCUDA_VISIBLE_DEVICES=%s\nLLAMA_CPP_LIB_PATH=%s\nLLAMA_TEST_MODEL=%s\n' \
      "$py" "$CUDA_VISIBLE_DEVICES" "$LLAMA_CPP_LIB_PATH" "$LLAMA_TEST_MODEL"
    if [ "$#" -gt 0 ]; then
      exec "$py" -m pytest "$@"
    fi
    exec "$py" -m pytest -o addopts='-rs' tests/ -q
  '';

  # Project 20: GPU-gated pytest against the P2 FORK lib (mixed-batch multi-LoRA).
  # Same proven CUDA env as project17-gpu-pytest, but LLAMA_CPP_LIB_PATH points at a
  # p2fork build so the seq-routing capability is present. After the step-7
  # refactor the reference owns no GPU-gated tests — the no-arg default runs the
  # framework suite; PROJECT20_FORK_LIB defaults to the Mode B
  # out-p2fork-24c5d3dbc lib (b10233 + P2 + hats + nan-fix). Pins GPU 0 by default
  # (GPU 1 often hosts a vLLM runner); override with PROJECT20_CUDA_DEVICES.
  # PROJECT20_SPIKE_PY selects the reference interpreter
  # (default .devenv/state/venv/bin/python). Args pass to pytest.
  scripts.project20-gpu-pytest.exec = ''
    set -euo pipefail
    root="$PWD"
    spike="$root/.scratch/projects/17-llama-cpp-inference-lab"
    py="''${PROJECT20_SPIKE_PY:-$PWD/.devenv/state/venv/bin/python}"
    model="''${PROJECT20_MODEL:-/home/nixuser/.cache/structured-agents/models/Ornith-1.0-9B-UD-Q4_K_XL.gguf}"
    lib="''${PROJECT20_FORK_LIB:-/home/nixuser/Documents/Projects/inferference/ci/build/.llamacpp-builds/out-p2fork-24c5d3dbc/lib}"
    cuda_ld="$(tr -d '\n' < "$spike/.cuda_runtime_ld")"
    if [ ! -x "$py" ]; then echo "reference python not found: $py (set PROJECT20_SPIKE_PY)" >&2; exit 2; fi
    if [ ! -f "$model" ]; then echo "model not found: $model (set PROJECT20_MODEL)" >&2; exit 2; fi
    if [ ! -d "$lib" ]; then echo "fork lib dir not found: $lib (set PROJECT20_FORK_LIB)" >&2; exit 2; fi
    export CUDA_VISIBLE_DEVICES="''${PROJECT20_CUDA_DEVICES:-0}"
    export LLAMA_CPP_LIB_PATH="$lib"
    export LLAMA_TEST_MODEL="$model"
    # /run/opengl-driver/lib first so the real libcuda wins over any CUDA stub;
    # cuda_ld carries gcc-lib (libstdc++) + cudart/cublas the bindings dlopen.
    export LD_LIBRARY_PATH="/run/opengl-driver/lib:$lib:$cuda_ld''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PYTHONPATH="src''${PYTHONPATH:+:$PYTHONPATH}"
    printf 'python=%s\nCUDA_VISIBLE_DEVICES=%s\nLLAMA_CPP_LIB_PATH=%s\nLLAMA_TEST_MODEL=%s\n' \
      "$py" "$CUDA_VISIBLE_DEVICES" "$LLAMA_CPP_LIB_PATH" "$LLAMA_TEST_MODEL"
    if [ "$#" -gt 0 ]; then
      exec "$py" -m pytest "$@"
    fi
    exec "$py" -m pytest -o addopts='-rs' tests/ -q
  '';

  # Project 23: cross-repo GPU contract suite. The inferference test suite is
  # the source of truth for the shared llama.cpp core; this runs it under the
  # inferference library venv, serialized on GPU 0 via the gpu-serialized flock
  # (GPU 1 often hosts a vLLM runner). LLAMA_CPP_LIB_PATH pins the Mode A unit
  # (the library venv's bundled lib dir — the report's reproduction recipe), so
  # the GPU-gated tests run instead of skip; the spike's .cuda_runtime_ld
  # carries the gcc/cudart/cublas libs the bindings dlopen. The reference keeps
  # no GPU-gated tests after the step-7 refactor — this is the GPU contract gate.
  scripts.project23-gpu-contract.exec = ''
    set -euo pipefail
    INF=/home/nixuser/Documents/Projects/inferference
    export LLAMA_CPP_LIB_PATH="$INF/ci/library/.venv/lib/python3.13/site-packages/llama_cpp/lib"
    cuda_ld="$(tr -d '\n' < "$PWD/.scratch/projects/17-llama-cpp-inference-lab/.cuda_runtime_ld")"
    export LD_LIBRARY_PATH="/run/opengl-driver/lib:$cuda_ld''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$INF/ci/runner/gpu-serialized.sh" "$INF/ci/library/.venv/bin/python" -m pytest "$INF/tests/" -q
  '';

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
  };

  enterShell = ''
    git --version
  '';
}

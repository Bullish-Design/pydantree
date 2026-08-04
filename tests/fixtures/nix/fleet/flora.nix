# Flora — repoman-enabled Python devenv.
#
# RepoMan is always on. This Python template is a superset of template-nix: it adds
# the `test` manager (testee — pytest / ruff / ty) to the language-agnostic core
# (copy + git), on top of the Python toolchain.
{ pkgs, config, lib, ... }:

let
  # Postgres for the image-dataset-curator tool (.scratch/projects/004). The curator
  # mines the restored Paloma prod dump; flora owns its own disposable restore so it
  # is self-contained (the dump file at ~/Downloads/paloma_db is the source of truth).
  # Port 5433 (NOT the default 5432) avoids colliding with any other local/Paloma PG.
  curatorDbName = "paloma_prod_restore";
  pgPort = toString config.services.postgres.port;
  pgHost = config.services.postgres.listen_addresses;

  # CUDA-only, sm_86-only llama.cpp. Both local GPUs are RTX 3060 (sm_86 / compute 8.6),
  # so we compile CUDA kernels for that ONE arch instead of nixpkgs' default 9-arch fan
  # (75;80;86;89;90;100;103;120;121) — ~9x less nvcc work per rebuild, identical runtime.
  # Re-import nixpkgs because the CUDA arch list is driven by `config.cudaCapabilities`,
  # not by an `.override` argument. CUDA (not Vulkan) is the faster backend on these NVIDIA
  # cards; nothing in-repo pins a Vulkan device, so we drop the Vulkan backend entirely.
  # Heavy CUDA toolkit deps come prebuilt from the configured cuda-maintainers.cachix.org
  # substituter, so only llama-cpp itself compiles.
  llamaCpp = (import pkgs.path {
    inherit (pkgs) system;
    config = { allowUnfree = true; cudaSupport = true; cudaCapabilities = [ "8.6" ]; };
  }).llama-cpp;
in
{
  # Per-machine toggle for GPU/server-only heaviness. Defaults on so the server is
  # unchanged. On a non-GPU machine (e.g. a laptop) drop an untracked devenv.local.nix
  # with `{ ... }: { flora.gpuHost = false; }` to skip the from-source CUDA llama.cpp
  # compile and the curator Postgres service. devenv auto-imports devenv.local.nix.
  options.flora.gpuHost = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = "Enable GPU/server-only components (CUDA llama.cpp, curator Postgres).";
  };

  config = {
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" ];
  # The prompt-dataset server binds to `tailscale ip -4`; make that CLI available
  # inside devenv's intentionally isolated PATH (rather than relying on /run/current-system).
  # llama.cpp (CUDA-only, sm_86 — see `llamaCpp` in the let block above) for running GGUF
  # models locally: the 070 gemma prompt-bank rewrite server and the 069 QC Qwen judge, now
  # both on `--device CUDA0`. Ships llama-server + llama-mtmd-cli (vision via libmtmd +
  # --mmproj). GGUFs live outside the store under .scratch (see scripts/qc_vlm_judge.py).
  packages = [
    pkgs.tailscale pkgs.docker pkgs.rsync pkgs.openssh
  ] ++ lib.optional config.flora.gpuHost llamaCpp;

  # Native shared libs that manylinux Python wheels (numpy / scipy / scikit-learn /
  # pillow / torch) dlopen at import time but which devenv's isolated environment does
  # not otherwise expose. Without this the venv's numpy fails at import with
  # `libz.so.1: cannot open shared object file`. This keeps host-side QC analysis
  # (scripts/qc_head_experiments.py, the `flora-qc-heads` entrypoint below) runnable
  # directly in the shell instead of needing a throwaway venv + manual LD_LIBRARY_PATH.
  #
  # /run/opengl-driver/lib carries the NVIDIA driver's libcuda.so.1 — it MUST come first
  # so the CUDA-13 torch wheel finds the driver and `torch.cuda.is_available()` is true
  # (the GPU path for high-res QC embedding, e.g. flora-qc-patchcore at 518px). Without
  # it torch silently falls back to CPU. It is a runtime path, not a nix-store output.
  env.LD_LIBRARY_PATH = "/run/opengl-driver/lib:" + pkgs.lib.makeLibraryPath [
    pkgs.zlib             # libz.so.1        — numpy, pillow, torch
    pkgs.stdenv.cc.cc.lib # libstdc++.so.6 + libgomp.so.1 — scipy / scikit-learn (OpenMP)
    pkgs.zstd             # libzstd.so.1     — numpy / torch compressed IO
    pkgs.libGL            # libGL.so.1 + libGLESv2.so.2 + libEGL.so.1 — opencv-python (cv2)
                          # and mediapipe Tasks C bindings (anime-detector QC spikes)
  ];

  # --- Image-dataset-curator (optional tool; see src/flora/curator + .scratch/004) ---
  # Postgres 17 to match the dump's server version; the package bundles the pg client
  # tools (pg_restore, createdb, psql) used for the one-time restore.
  services.postgres = lib.mkIf config.flora.gpuHost {
    enable = true;
    package = pkgs.postgresql_17;
    initialDatabases = [ { name = curatorDbName; } ];
    listen_addresses = "127.0.0.1";
    port = 5433;
  };

  # DSN the curator reads by default (override CURATOR_DSN to point elsewhere).
  env.CURATOR_DSN = "host=${pgHost} port=${pgPort} dbname=${curatorDbName}";

  # Pin the keepers output dir to the repo root so it's deterministic regardless of
  # the process's CWD (gitignored: /keepers/). Override CURATOR_OUTPUT_DIR to relocate.
  env.CURATOR_OUTPUT_DIR = "${config.env.DEVENV_ROOT}/keepers";

  # Curator web app entrypoint. `devenv up` supervises it alongside postgres; the app
  # connects to postgres on startup (it materializes the human-selected helper table in
  # its FastAPI lifespan), so guard the launch on postgres being ready first. This
  # devenv uses the native process manager (no process-compose depends_on), so the wait
  # lives in the exec. `exec` hands the PID to uvicorn so devenv's signals reach it.
  # Needs the curator extra installed once: devenv shell -- uv pip install -e '.[curator]'
  processes.curator = lib.mkIf config.flora.gpuHost {
    exec = ''
      echo "[curator] waiting for postgres at ${pgHost}:${pgPort} ..."
      until pg_isready -h ${pgHost} -p ${pgPort} >/dev/null 2>&1; do sleep 1; done
      exec python -m flora.web.acquire
    '';
  };

  # Serve the DB-free prompt-dataset curator over Tailscale. This deliberately skips
  # the Postgres readiness wait above: `--source jsonl:` reads the transferred exports
  # directly. It binds to this machine's Tailscale IP (not 0.0.0.0), so it is reachable
  # from tailnet peers without also exposing the unauthenticated curator on the LAN.
  # Run locally or through SSH: `devenv shell -- flora-curator-prompt-dataset`.
  # CURATOR_HOST / CURATOR_PORT remain overrideable for an explicit bind or port.
  scripts.flora-curator-prompt-dataset.exec = ''
    if [ -z "''${CURATOR_HOST:-}" ]; then
      CURATOR_HOST="$(tailscale ip -4)"
      if [ -z "$CURATOR_HOST" ]; then
        echo "No Tailscale IPv4 address found; connect this server to Tailscale or set CURATOR_HOST explicitly." >&2
        exit 1
      fi
      export CURATOR_HOST
    fi
    exec python -m flora.web.acquire \
      --source "jsonl:$DEVENV_ROOT/datasets/paloma_prompt_dataset"
  '';

  # YAML-selected annotation services. They deliberately run as separate processes:
  # tag review stays lightweight on :8110 while SAM2's lazy model/GPU state is isolated
  # on :8100. Both bind only to this node's Tailscale IPv4 by default; a caller can
  # explicitly override FLORA_CURATION_HOST for localhost-only troubleshooting.
  #
  # Install once in this devenv: uv pip install -e '.[curation]'; the SAM service
  # additionally needs: uv pip install -e '.[curation-sam]'.
  # Usage: devenv shell -- flora-curation-tag
  #        devenv shell -- flora-curation-sam
  scripts.flora-curation-tag.exec = ''
    set -eu
    port="''${FLORA_CURATION_TAG_PORT:-8110}"
    listener="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
    if [ -n "$listener" ]; then
      pid="$(printf '%s\n' "$listener" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
      command="$(test -n "$pid" && ps -p "$pid" -o args= 2>/dev/null || true)"
      echo "Port $port is already in use''${pid:+ by PID $pid}: ''${command:-unknown listener}" >&2
      if [ ! -t 0 ]; then
        echo "Refusing to replace an existing session without an interactive confirmation." >&2
        exit 1
      fi
      printf "Replace this session with Flora's tag curation service? [y/N] " >&2
      read -r answer
      case "$answer" in
        y|Y|yes|YES)
          test -n "$pid" || { echo "Could not identify the listener PID; not replacing it." >&2; exit 1; }
          kill -TERM "$pid"
          for _ in $(seq 1 20); do
            ss -H -ltn "sport = :$port" | grep -q . || break
            sleep 1
          done
          ss -H -ltn "sport = :$port" | grep -q . && { echo "Existing session did not stop within 20 seconds." >&2; exit 1; }
          ;;
        *) echo "Existing session left running." >&2; exit 0 ;;
      esac
    fi
    if [ -z "''${FLORA_CURATION_HOST:-}" ]; then
      FLORA_CURATION_HOST="$(tailscale ip -4)"
      if [ -z "$FLORA_CURATION_HOST" ]; then
        echo "No Tailscale IPv4 address found; connect this server to Tailscale or set FLORA_CURATION_HOST explicitly." >&2
        exit 1
      fi
      export FLORA_CURATION_HOST
    fi
    export FLORA_CURATION_TEMPLATES="''${FLORA_CURATION_TEMPLATES:-$DEVENV_ROOT/curation-templates}"
    exec python -m flora.web.annotate.app --workflow tag --port "$port"
  '';

  scripts.flora-curation-sam.exec = ''
    set -eu
    port="''${FLORA_CURATION_SAM_PORT:-8100}"
    listener="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
    if [ -n "$listener" ]; then
      pid="$(printf '%s\n' "$listener" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
      command="$(test -n "$pid" && ps -p "$pid" -o args= 2>/dev/null || true)"
      echo "Port $port is already in use''${pid:+ by PID $pid}: ''${command:-unknown listener}" >&2
      if [ ! -t 0 ]; then
        echo "Refusing to replace an existing session without an interactive confirmation." >&2
        exit 1
      fi
      printf "Replace this session with Flora's SAM curation service? [y/N] " >&2
      read -r answer
      case "$answer" in
        y|Y|yes|YES)
          test -n "$pid" || { echo "Could not identify the listener PID; not replacing it." >&2; exit 1; }
          kill -TERM "$pid"
          for _ in $(seq 1 20); do
            ss -H -ltn "sport = :$port" | grep -q . || break
            sleep 1
          done
          ss -H -ltn "sport = :$port" | grep -q . && { echo "Existing session did not stop within 20 seconds." >&2; exit 1; }
          ;;
        *) echo "Existing session left running." >&2; exit 0 ;;
      esac
    fi
    if [ -z "''${FLORA_CURATION_HOST:-}" ]; then
      FLORA_CURATION_HOST="$(tailscale ip -4)"
      if [ -z "$FLORA_CURATION_HOST" ]; then
        echo "No Tailscale IPv4 address found; connect this server to Tailscale or set FLORA_CURATION_HOST explicitly." >&2
        exit 1
      fi
      export FLORA_CURATION_HOST
    fi
    export FLORA_CURATION_TEMPLATES="''${FLORA_CURATION_TEMPLATES:-$DEVENV_ROOT/curation-templates}"
    exec python -m flora.web.annotate.app --workflow sam --port "$port"
  '';

  # Browser-side MobileSAM annotation server (experimental, no GPU needed).
  # Runs ONNX runtime entirely in the browser via WebGPU.
  # Usage: devenv shell -- flora-browser-sam              # spike mode
  #        devenv shell -- flora-browser-sam --full       # with records/images
  scripts.flora-browser-sam.exec = ''
    set -eu
    port="''${QC_ANNO_PORT:-8103}"
    listener="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
    if [ -n "$listener" ]; then
      pid="$(printf '%s\n' "$listener" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
      command="$(test -n "$pid" && ps -p "$pid" -o args= 2>/dev/null || true)"
      echo "Port $port is already in use''${pid:+ by PID $pid}: ''${command:-unknown listener}" >&2
      if [ ! -t 0 ]; then
        echo "Refusing to replace an existing session without an interactive confirmation." >&2
        exit 1
      fi
      printf "Replace this session with Flora's browser SAM service? [y/N] " >&2
      read -r answer
      case "$answer" in
        y|Y|yes|YES)
          test -n "$pid" || { echo "Could not identify the listener PID; not replacing it." >&2; exit 1; }
          kill -TERM "$pid"
          for _ in $(seq 1 20); do
            ss -H -ltn "sport = :$port" | grep -q . || break
            sleep 1
          done
          ss -H -ltn "sport = :$port" | grep -q . && { echo "Existing session did not stop within 20 seconds." >&2; exit 1; }
          ;;
        *) echo "Existing session left running." >&2; exit 0 ;;
      esac
    fi
    exec "$DEVENV_ROOT/experiments/browser-sam-annotator/run.sh" "$@"
  '';

  # Layer selection curation (Qwen-Image-Layered outputs).
  # Usage: devenv shell -- flora-curation-layers
  scripts.flora-curation-layers.exec = ''
    set -eu
    port="''${FLORA_CURATION_LAYERS_PORT:-8120}"
    listener="$(ss -H -ltnp "sport = :$port" 2>/dev/null || true)"
    if [ -n "$listener" ]; then
      pid="$(printf '%s\n' "$listener" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)"
      command="$(test -n "$pid" && ps -p "$pid" -o args= 2>/dev/null || true)"
      echo "Port $port is already in use''${pid:+ by PID $pid}: ''${command:-unknown listener}" >&2
      if [ ! -t 0 ]; then
        echo "Refusing to replace an existing session without an interactive confirmation." >&2
        exit 1
      fi
      printf "Replace this session with Flora's layers curation service? [y/N] " >&2
      read -r answer
      case "$answer" in
        y|Y|yes|YES)
          test -n "$pid" || { echo "Could not identify the listener PID; not replacing it." >&2; exit 1; }
          kill -TERM "$pid"
          for _ in $(seq 1 20); do
            ss -H -ltn "sport = :$port" | grep -q . || break
            sleep 1
          done
          ss -H -ltn "sport = :$port" | grep -q . && { echo "Existing session did not stop within 20 seconds." >&2; exit 1; }
          ;;
        *) echo "Existing session left running." >&2; exit 0 ;;
      esac
    fi
    if [ -z "''${FLORA_CURATION_HOST:-}" ]; then
      FLORA_CURATION_HOST="$(tailscale ip -4)"
      if [ -z "$FLORA_CURATION_HOST" ]; then
        echo "No Tailscale IPv4 address found; connect this server to Tailscale or set FLORA_CURATION_HOST explicitly." >&2
        exit 1
      fi
      export FLORA_CURATION_HOST
    fi
    export FLORA_CURATION_TEMPLATES="''${FLORA_CURATION_TEMPLATES:-$DEVENV_ROOT/curation-templates}"
    exec python -m flora.web.annotate.layers_app --port "$port"
  '';

  # Local DINOv2 QC entrypoint (also the default for `flora qc run`). Usage:
  #   flora-qc-local qc_records.jsonl --image-res 518 --features cls_mean_max
  # `flora qc run` performs CUDA preflight itself; the local runner retries the
  # explicit NVIDIA CDI device on hosts where Docker misroutes `--gpus all`.
  scripts.flora-qc-local.exec = ''
    exec flora qc run --runner local "$@"
  '';

  # Copy the newest run directories to the matching checkout on the server.
  # Usage: `devenv shell -- flora-sync-latest-runs 5`.
  # Set FLORA_RUNS_SYNC_DEST to use a different SSH destination.
  scripts.flora-sync-latest-runs.exec = ''
    set -eu

    if [ "$#" -ne 1 ]; then
      echo "Usage: flora-sync-latest-runs <positive-integer>" >&2
      exit 2
    fi

    case "x$1" in
      x|*[!0-9]*)
        echo "Usage: flora-sync-latest-runs <positive-integer>" >&2
        exit 2
        ;;
    esac

    if [ "$1" -eq 0 ]; then
      echo "Usage: flora-sync-latest-runs <positive-integer>" >&2
      exit 2
    fi

    count="$1"
    destination="''${FLORA_RUNS_SYNC_DEST:-andrew@server:$DEVENV_ROOT/}"
    run_list="$(mktemp)"
    trap 'rm -f "$run_list"' EXIT

    cd "$DEVENV_ROOT"
    find runs -mindepth 1 -maxdepth 1 -type d -printf '%T@:%p\\0' \
      | sort -znr \
      | head -zn "$count" \
      | cut -z -d: -f2- > "$run_list"

    if [ ! -s "$run_list" ]; then
      echo "No run directories found in $DEVENV_ROOT/runs." >&2
      exit 1
    fi

    rsync -avh --progress --from0 --files-from="$run_list" ./ "$destination"
  '';

  # Mirror the quality-control dataset to the matching checkout on the server.
  # Usage: `devenv shell -- flora-sync-quality-control`.
  # Set FLORA_QUALITY_CONTROL_SYNC_DEST to use a different SSH destination.
  scripts.flora-sync-quality-control.exec = ''
    set -eu

    if [ "$#" -ne 0 ]; then
      echo "Usage: flora-sync-quality-control" >&2
      exit 2
    fi

    destination="''${FLORA_QUALITY_CONTROL_SYNC_DEST:-andrew@server:$DEVENV_ROOT/datasets/quality_control/}"
    source_dir="$DEVENV_ROOT/datasets/quality_control"

    if [ ! -d "$source_dir" ]; then
      echo "Quality-control dataset directory not found: $source_dir" >&2
      exit 1
    fi

    rsync -avh --progress "$source_dir/" "$destination"
  '';

  # Host-side QC "better heads" experiments (069 alt-approach guide 08/03): compare
  # Mahalanobis / distance-to-good / graded-kNN / CV-logreg heads against the probe's
  # logreg baseline over a probe's CACHED embeddings.npz. Pure post-processing — CPU
  # only, no pod, no re-embed. Needs the `qc` extra: uv pip install -e '.[qc]'. Usage:
  #   flora-qc-heads runs/<run>/output/embeddings.npz
  # 089 phase 4 (M7): the harness moved into flora_qc (core/eval.py — the eval + U3 sink).
  scripts.flora-qc-heads.exec = ''
    exec python -m flora_qc.core.eval heads "$@"
  '';

  # Host-side PatchCore / PaDiM memory-bank anomaly detection (069 alt-approach guide
  # 08/02). Re-embeds the corpus to recover DINOv2 patch grids (CPU on the host), builds
  # a good-only coreset memory bank, and scores defect-likelihood by max patch distance.
  # Needs the `qc` + `qc-embed` extras: uv pip install -e '.[qc,qc-embed]'. Usage:
  #   flora-qc-patchcore runs/<run>/dataset/records.jsonl runs/<run>/dataset/images
  # 089 phase 3: the module moved into flora_qc (models/anomaly/patchcore.py).
  scripts.flora-qc-patchcore.exec = ''
    exec python -m flora_qc.models.anomaly.patchcore "$@"
  '';

  # Serve the 069 fast-QC model-output overlay viewer (scripts/qc_model_viewer.html). Runs a
  # static server from repo root so the viewer can fetch both the overlay JSON and the corpus
  # images by their repo-relative paths. Usage: `flora-qc-viewer [PORT]` (default 8000). The
  # viewer auto-loads .scratch/projects/069/fast-qc/overlays/overlays.json — regenerate that
  # with `python scripts/qc_dump_model_overlays.py` when the corpus or models change.
  scripts.flora-qc-viewer.exec = ''
    set -eu
    PORT="''${1:-8000}"
    OVERLAYS="$DEVENV_ROOT/.scratch/projects/069/fast-qc/overlays/overlays.json"
    if [ ! -f "$OVERLAYS" ]; then
      echo "note: overlays.json missing at $OVERLAYS — the viewer will start empty." >&2
      echo "      generate it with: python scripts/qc_dump_model_overlays.py" >&2
    fi
    echo "QC model viewer → http://localhost:$PORT/scripts/qc_model_viewer.html"
    cd "$DEVENV_ROOT"
    exec python -m http.server "$PORT"
  '';

  # Build the offline 076 pipeline-demo client deliverable (report_generator/).
  # Renders content.md (prose) + data.yaml (structured data) through the Jinja
  # template into one self-contained report_generator/dist/076-pipeline-demo/demo.html
  # with every image embedded as a base64 data: URI (share the file directly — no
  # assets/ dir, no zip). Pure-Python, offline, no network. Usage:
  #   devenv shell -- flora-build-pipeline-report            # build the self-contained demo.html
  #   devenv shell -- flora-build-pipeline-report --check    # validate only, no writes
  # 089 phase 7 (the §5 tests seam): hypothesis + syrupy are ENTRYPOINT-INSTALLED —
  # flora-only, never in the base venv requirements (no checksum churn), never in testee's
  # deps (the import-linter console-script rationale doesn't apply to pytest-imported
  # libraries), never on the wheel. The property/snapshot test modules importorskip when
  # the libs are absent, so the base suite stays green (2 modules skipped); this entrypoint
  # is the sanctioned way to run them. uv pip install targets the devenv venv (VIRTUAL_ENV
  # is set by devenv), is idempotent (no-op when already satisfied), and self-heals if a
  # future venv re-init wipes the libs. Usage:
  #   devenv shell -- flora-qc-tests-extra tests/flora_qc -q
  scripts.flora-qc-tests-extra.exec = ''
    uv pip install "hypothesis>=6.100" "syrupy>=4.6"
    exec python -m pytest "$@"
  '';

  scripts.flora-build-pipeline-report.exec = ''
    exec python "$DEVENV_ROOT/report_generator/build.py" "$@"
  '';

  # Read-only comparison viewer. `devenv up studio` supervises `flora studio --view-session`,
  # serving the compare UI over already-rendered eval sessions under runs/ (pick the session in
  # the UI dropdown). VIEW mode creates NO RunPod pod and needs no RUNPOD_API_KEY: a pod is only
  # booted by the live grid's start-session/generate path, which view mode never triggers — this
  # is a pure local file server. Override FLORA_VIEW_SESSION / FLORA_STUDIO_PORT to point elsewhere.
  # `exec` hands the PID to uvicorn so devenv's signals reach it.
  processes.studio.exec = ''
    exec python -m flora.cli studio --host 127.0.0.1 \
      --port ''${FLORA_STUDIO_PORT:-8011} \
      --view-session ''${FLORA_VIEW_SESSION:-runs/evals/db-picked-3mo}
  '';

  # Self-contained Replicate prompt-experiment lab. Its dependencies are deliberately
  # isolated from Flora: `uv run --project` uses the lab's own pyproject.toml.
  # It binds only to loopback unless a trusted Tailscale address is explicitly supplied.
  processes.replicate-prompt-experiments.exec = ''
    exec uv run --project "$DEVENV_ROOT/.scratch/projects/061-replicate-prompt-experiments" \
      python "$DEVENV_ROOT/.scratch/projects/061-replicate-prompt-experiments/serve.py" \
      --host "''${REPLICATE_PROMPT_EXPERIMENTS_HOST:-127.0.0.1}" \
      --port "''${REPLICATE_PROMPT_EXPERIMENTS_PORT:-8013}"
  '';

  # Install pyjutsu from vendomat's prebuilt wheelhouse instead of building ../Pyjutsu's
  # maturin extension when repoman-sync installs the manager CLIs (gitman depends on
  # pyjutsu). UV_FIND_LINKS + UV_NO_BUILD_PACKAGE come from the imported vendomat module.
  # sharedCargo = false: flora compiles no Rust of its own, so no sccache/CARGO_TARGET_DIR.
  vendor = {
    enable = true;
    libs = [ "pyjutsu" ];
    sharedCargo = false;
  };

  # Python toolchain. The venv also hosts the manager CLIs (copyroom, gitman,
  # testee) that repoman-sync installs from repoman.lock.
  languages.python = {
    enable = true;
    venv.enable = true;
    # The QC stack (089 Phase 0) — declared here so a fresh checkout yields a working
    # flora_qc environment with zero manual steps. venv.requirements is the ADDITIVE,
    # checksum-gated mechanism (uv pip install -r on init) — deliberately NOT uv.sync:
    # uv sync would PRUNE every package outside uv.lock, and the repoman manager CLIs
    # (testee/gitman/repoman/copyroom) are uv-pip-installed, not locked. The forwarding
    # extras resolve flora-qc (the uv workspace member) EDITABLE, so dev edits to
    # src/flora_qc are live. import-linter is declared here too (belt-and-suspenders;
    # repoman-sync also brings it via testee's deps).
    venv.requirements = ''
      -e .[qc,qc-embed,matte]
      import-linter>=2.0
    '';
    uv.enable = true;
  };

  # --- Local CUDA-container workflow ------------------------------------
  # The daemon and NVIDIA driver remain host-managed. These task entrypoints make
  # the project-side contract reproducible without putting Docker/Podman SDKs in
  # Flora's Python dependencies. FLORA_CONTAINER_RUNTIME chooses docker|podman;
  # otherwise Docker is preferred and Podman is the fallback, matching flora.local.
  tasks = {
    "flora:local-preflight".exec = ''
      set -eu
      runtime="''${FLORA_CONTAINER_RUNTIME:-}"
      if [ -z "$runtime" ]; then
        if command -v docker >/dev/null 2>&1; then runtime=docker
        elif command -v podman >/dev/null 2>&1; then runtime=podman
        else
          echo "No Docker or Podman executable found. Install one, then set FLORA_CONTAINER_RUNTIME." >&2
          exit 1
        fi
      fi
      case "$runtime" in docker|podman) ;; *)
        echo "FLORA_CONTAINER_RUNTIME must be docker or podman (got $runtime)." >&2; exit 1;; esac
      image="''${FLORA_LOCAL_AITOOLKIT_IMAGE:-ostris/aitoolkit:0.10.19}"
      "$runtime" info >/dev/null
      if [ "$runtime" = docker ]; then
        # The managed host uses Docker CDI. Explicit NVIDIA selection avoids its
        # broken generic --gpus-all → AMD CDI resolution (verified 2026-07-24).
        "$runtime" run --rm --device nvidia.com/gpu=all "$image" nvidia-smi -L
      else
        "$runtime" run --rm --device nvidia.com/gpu=all "$image" nvidia-smi -L
      fi
    '';

    # Builds a deliberately thin local derivative. The Dockerfile centralizes the
    # future customization point while preserving the exact ai-toolkit base today.
    "flora:local-image-build".exec = ''
      set -eu
      runtime="''${FLORA_CONTAINER_RUNTIME:-}"
      if [ -z "$runtime" ]; then
        if command -v docker >/dev/null 2>&1; then runtime=docker
        elif command -v podman >/dev/null 2>&1; then runtime=podman
        else
          echo "No Docker or Podman executable found. Install one, then set FLORA_CONTAINER_RUNTIME." >&2
          exit 1
        fi
      fi
      case "$runtime" in docker|podman) ;; *)
        echo "FLORA_CONTAINER_RUNTIME must be docker or podman (got $runtime)." >&2; exit 1;; esac
      base_image="''${FLORA_AITOOLKIT_BASE_IMAGE:-ostris/aitoolkit:0.10.19}"
      local_image="''${FLORA_LOCAL_AITOOLKIT_IMAGE:-flora/aitoolkit:local}"
      "$runtime" build --build-arg "BASE_IMAGE=$base_image" --tag "$local_image" \
        --file "$DEVENV_ROOT/containers/aitoolkit.Dockerfile" "$DEVENV_ROOT"
      echo "Built $local_image. Export FLORA_LOCAL_AITOOLKIT_IMAGE=$local_image for runner: local."
    '';
  };
  };
}

{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env = {
    GREET = "terminal-state development environment";
    # Ensure tmux socket directory exists
    TMUX_TMPDIR = "${config.env.DEVENV_ROOT}/.tmux";
  };

  # https://devenv.sh/packages/
  packages = with pkgs; [
    # Core terminal tools
    tmux # Required for libtmux backend
    asciinema # Terminal session recorder
    agg # Asciinema to GIF converter (modern, fast)

    # Image and font support
    imagemagick # Image processing utilities
    ghostscript # PostScript/PDF interpreter (for imagemagick)

    # Fonts for terminal rendering
    dejavu_fonts # DejaVu fonts
    liberation_ttf # Liberation fonts
    source-code-pro # Source Code Pro monospace font

    # Utilities
    git # Version control
    curl # HTTP client
    jq # JSON processor
  ];

  # https://devenv.sh/scripts/
  scripts = {
    # Record terminal session with asciinema
    record-terminal = {
      exec = ''
        echo "Recording terminal session..."
        echo "Press Ctrl+D or type 'exit' to stop recording"
        asciinema rec "$@"
      '';
      description = "Record terminal session with asciinema";
    };

    # Convert asciinema recording to GIF
    cast-to-gif = {
      exec = ''
        if [ -z "$1" ] || [ -z "$2" ]; then
          echo "Usage: cast-to-gif <input.cast> <output.gif>"
          exit 1
        fi
        echo "Converting $1 to $2..."
        agg "$1" "$2"
      '';
      description = "Convert asciinema recording (.cast) to GIF";
    };

    # Play asciinema recording
    play-cast = {
      exec = ''
        if [ -z "$1" ]; then
          echo "Usage: play-cast <recording.cast>"
          exit 1
        fi
        asciinema play "$1"
      '';
      description = "Play asciinema recording";
    };

    # Run tests with coverage
    test = {
      exec = ''
        pytest "$@"
      '';
      description = "Run tests with pytest";
    };

    # Format code
    format = {
      exec = ''
        echo "Formatting Python code with black..."
        black src/ tests/
        echo "Done!"
      '';
      description = "Format code with black";
    };

    # Lint code
    lint = {
      exec = ''
        echo "Linting with ruff..."
        ruff check src/ tests/
        echo "Type checking with mypy..."
        mypy src/
      '';
      description = "Lint code with ruff and mypy";
    };

    # Build the package
    build-package = {
      exec = ''
        echo "Building package..."
        python -m build
      '';
      description = "Build the Python package";
    };
  };

  # https://devenv.sh/languages/
  languages = {
    python = {
      enable = true;
      version = "3.11";
      venv.enable = true;
      uv.enable = true;

      # Python packages
      # Note: The main dependencies are installed via pyproject.toml
      # These are additional system-level tools
    };
  };

  # https://devenv.sh/processes/
  # processes = {
  #   ping.exec = "ping example.com";
  # };

  # https://devenv.sh/services/
  # services = {
  # };

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks = {
  #   # Python formatting
  #   black.enable = true;

  #   # Python linting
  #   ruff.enable = true;

  #   # Type checking
  #   mypy = {
  #     enable = true;
  #     settings = {
  #       binPath = "mypy";
  #     };
  #   };

  #   # Nix formatting
  #   nixpkgs-fmt.enable = true;
  # };

  # https://devenv.sh/enterShell/
  enterShell = ''
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         terminal-state Development Environment             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📦 Project: terminal-state"
    echo "🐍 Python: $(python --version)"
    echo "🖥️  tmux: $(tmux -V)"
    echo "🎬 asciinema: $(asciinema --version)"
    echo ""
    echo "Available commands:"
    echo "  record-terminal     - Record terminal session with asciinema"
    echo "  cast-to-gif         - Convert .cast to .gif"
    echo "  play-cast           - Play asciinema recording"
    echo "  test                - Run pytest tests"
    echo "  format              - Format code with black"
    echo "  lint                - Lint code with ruff and mypy"
    echo "  build-package       - Build the Python package"
    echo ""
    echo "Quick start:"
    echo "  1. Install dependencies: uv sync --all-extras"
    echo "  2. Run tests: test"
    echo "  3. Try recording: record-terminal demo.cast"
    echo "  4. Convert to GIF: cast-to-gif demo.cast demo.gif"
    echo ""

    # Create tmux socket directory if it doesn't exist
    mkdir -p "${config.env.DEVENV_ROOT}/.tmux"
    echo ""
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # See full reference at https://devenv.sh/reference/options/
}

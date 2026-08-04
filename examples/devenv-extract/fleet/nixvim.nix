{ pkgs, lib, config, ... }:
let
  cfg = config.nv2;

  # Build mini.nvim from source (pinned release)
  mini-nvim = pkgs.vimUtils.buildVimPlugin {
    pname = "mini.nvim";
    version = "0.17.0";
    src = pkgs.fetchFromGitHub {
      owner = "echasnovski";
      repo = "mini.nvim";
      rev = "v0.17.0";
      hash = "sha256-xmNZrQDptaNcECHSGtjownFyR1qxsP7lge8OAIFe8BU=";
    };
  };

  # All plugins from shared plugin list
  allPlugins = import ./plugins.nix { inherit pkgs; };

  # Bundle nvim-treesitter with grammars (replaces ensure_installed / auto_install)
  treesitterWithGrammars = pkgs.vimPlugins.nvim-treesitter.withPlugins (p:
    cfg.treesitterGrammars p
  );

  # Replace the bare nvim-treesitter in allPlugins with the grammar-bundled version
  pluginsWithGrammars = map (p:
    if (p.pname or "") == "nvim-treesitter"
    then treesitterWithGrammars
    else p
  ) allPlugins;

  # Combine base plugins with any extra plugins from consumer projects
  finalPlugins = [ mini-nvim ] ++ pluginsWithGrammars ++ cfg.extraPlugins;

  # Build a properly wrapped Neovim with all plugins in packpath
  neovimConfig = pkgs.neovimUtils.makeNeovimConfig {
    plugins = map (p: { plugin = p; }) finalPlugins;
  };

  neovim = pkgs.wrapNeovimUnstable pkgs.neovim-unwrapped (neovimConfig // {
    # Don't generate an init.vim/lua - we use our own
    neovimRcContent = "";
    luaRcContent = "";
  });

  # Resolve the nvim config directory at Nix eval time so it works both
  # locally (path to the repo checkout) and when imported from another
  # project (path inside the Nix store).
  nvimConfigDir = builtins.toString ./nvim;

  # Build the extra --cmd flags for additional runtimepath entries.
  # Consumer projects use this to inject local plugin directories.
  extraRtpArgs = lib.concatMapStringsSep " \\\n    "
    (p: ''--cmd "set rtp^=${p}"'')
    cfg.extraRuntimePaths;

  # Build an --cmd flag that writes all extraInitLua into a temp file
  # and sources it. This runs *after* init.lua has loaded.
  extraInitFlag = lib.optionalString (cfg.extraInitLua != "") (
    let
      extraInitFile = pkgs.writeText "nv2-extra-init.lua" cfg.extraInitLua;
    in
      ''-c "luafile ${extraInitFile}"''
  );

  # Environment variable flags for the nv2 wrapper script
  envVarExports = lib.concatStringsSep "\n"
    (lib.mapAttrsToList (name: value: "export ${name}=${lib.escapeShellArg value}") cfg.env);
in
{
  options.nv2 = {
    extraPlugins = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default = [];
      description = ''
        Additional Vim plugin packages to include in the wrapped Neovim.
        These are added to the packpath alongside the base plugin set.
      '';
      example = lib.literalExpression ''
        [
          pkgs.vimPlugins.vim-fugitive
          (pkgs.vimUtils.buildVimPlugin {
            pname = "my-plugin";
            version = "0.1.0";
            src = ./path/to/plugin;
          })
        ]
      '';
    };

    extraRuntimePaths = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      description = ''
        Additional paths to prepend to Neovim's runtimepath at startup.
        Use this to add local plugin development directories or project-
        specific Lua modules without rebuilding the Nix derivation.
      '';
      example = lib.literalExpression ''
        [ (builtins.toString ./.) ]
      '';
    };

    extraInitLua = lib.mkOption {
      type = lib.types.lines;
      default = "";
      description = ''
        Extra Lua code to execute after the base init.lua has loaded.
        This is written to a file in the Nix store and sourced via
        `nvim -c "luafile ..."`. Use this for per-project overrides
        such as colorscheme changes, environment variables, additional
        plugin setup, or LSP configuration adjustments.
      '';
      example = ''
        -- Override the colorscheme for this project
        require("mini.hues").setup({
          background = "#1a1b26",
          foreground = "#c0caf5",
          accent = "cyan",
        })

        -- Set project-specific env vars for codecompanion
        vim.env.ANTHROPIC_API_KEY = vim.fn.system("pass show api/anthropic"):gsub("%s+$", "")
      '';
    };

    treesitterGrammars = lib.mkOption {
      type = lib.types.functionTo (lib.types.listOf lib.types.package);
      default = p: [
        p.lua p.vim p.vimdoc p.python p.nix p.rust p.go
        p.javascript p.typescript p.tsx p.json p.yaml
        p.html p.css p.markdown p.markdown_inline
        p.bash p.c p.cpp
      ];
      description = ''
        A function that takes the treesitter grammar set and returns a
        list of grammars to bundle. Override this to add or replace
        grammars for project-specific languages.
      '';
      example = lib.literalExpression ''
        p: [
          p.lua p.python p.nix p.rust
          p.haskell p.elixir p.zig
        ]
      '';
    };

    env = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = {};
      description = ''
        Environment variables to export before launching Neovim.
        Useful for setting API keys, configuration flags, or
        tool-specific variables on a per-project basis.
      '';
      example = lib.literalExpression ''
        {
          ANTHROPIC_API_KEY = "sk-ant-...";
          CODECOMPANION_ADAPTER = "openai";
        }
      '';
    };

    extraPackages = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default = [];
      description = ''
        Additional packages to add to the devenv environment alongside
        the base LSP servers, formatters, and linters. Use this for
        project-specific tooling that Neovim needs on PATH.
      '';
      example = lib.literalExpression ''
        with pkgs; [
          haskell-language-server
          ormolu
          hlint
        ]
      '';
    };
  };

  config = {
    # Core packages
    packages = [
      neovim
    ] ++ (with pkgs; [
      git
      ripgrep
      fd

      # LSP servers
      lua-language-server
      nil
      bash-language-server
      pyright
      rust-analyzer
      clang-tools  # includes clangd
      gopls
      nodePackages.typescript-language-server
      nodePackages.vscode-langservers-extracted

      # Formatters
      stylua
      alejandra
      ruff
      prettierd
      goimports-reviser
      nixfmt

      # Linters
      shellcheck
      statix
      yamllint
      selene
      golangci-lint

      # DAP adapters
      python3Packages.debugpy

      # Optional
      nodePackages.markdownlint-cli2
    ]) ++ cfg.extraPackages;

    # Startup command: launch the wrapped neovim with our config
    scripts.nv2.exec = ''
      ${envVarExports}
      exec ${neovim}/bin/nvim \
        --cmd "set rtp^=${nvimConfigDir}" \
        ${lib.optionalString (cfg.extraRuntimePaths != []) extraRtpArgs} \
        -u "${nvimConfigDir}/init.lua" \
        ${extraInitFlag} \
        "$@"
    '';

    # Show helpful message on shell entry
    enterShell = ''
      echo "nv2 ready - run 'nv2' to launch Neovim"
    '';
  };
}

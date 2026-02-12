{ pkgs, ... }:

{
  env.GREET = "pydantree";

  packages = [
    pkgs.git
    pkgs.tree-sitter
  ];

  languages = {
    python = {
      enable = true;
      version = "3.13";
      venv.enable = true;
      uv.enable = true;
    };
  };

  scripts.hello.exec = ''
    echo "hello from $GREET"
  '';

  enterShell = ''
    hello
    git --version
    tree-sitter --version
  '';

  enterTest = ''
    git --version | grep --color=auto "${pkgs.git.version}"
    tree-sitter --version
  '';
}

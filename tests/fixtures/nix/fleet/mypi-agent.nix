{ pkgs, ... }:
{
  imports = [ ./modules/pi-agent.nix ];

  packages = [
    pkgs.secretspec
  ];
}

# SPDX-FileCopyrightText: 2025 karmar <karmar@posteo.de>
# SPDX-License-Identifier: CC-BY-SA-4.0

{
  system ? builtins.currentSystem,
  sources ? import ./npins,
}:
let
  pkgs = import sources.nixpkgs {
    config = { };
    overlays = [ ];
    inherit system;
  };

  inherit (pkgs) lib;

in
lib.makeScope pkgs.newScope (final: {
  shell = pkgs.mkShell {
    packages = with pkgs; [
      npins
      reuse
    ];
  };
})

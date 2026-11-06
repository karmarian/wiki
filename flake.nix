# SPDX-FileCopyrightText: 2026 karmar <karmar@posteo.de>
# SPDX-License-Identifier: GPL-3.0-or-later

{
  description = "karmarian/wiki org-roam notes -> Zola static site";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      lib = nixpkgs.lib;

      sourceFiles = lib.fileset.unions [
        (lib.fileset.fileFilter (file: file.hasExt "org") ./.)
        (lib.fileset.maybeMissing ./LICENSES)
      ];

      src = lib.fileset.toSource {
        root = ./.;
        fileset = sourceFiles;
      };

      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
    in
    {
      packages = lib.genAttrs systems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.callPackage ./site.nix {
            inherit src;
            baseUrl = "https://karmarian.gitlab.io/wiki/";
          };
        }
      );

      devShells = lib.genAttrs systems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.just
              pkgs.zola
              pkgs.pandoc
              pkgs.python3
              pkgs.reuse
            ];

            shellHook = ''
              echo "karmarian/wiki dev shell"
              echo "  \`just -l\` lists all recipes — try: just s"
              just --list || true
            '';
          };
        }
      );
    };
}

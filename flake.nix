{
  # ==========================================================================
  # karmarian/wiki — org-roam notes -> Zola static site
  #
  #   nix build .#default   build deployable site artifacts (result/)
  #   nix develop           dev shell: `serve`, `regenerate-site`, `reuse lint`
  # ==========================================================================
  description = "karmarian/wiki org-roam notes -> Zola static site";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      lib = nixpkgs.lib;

      # ------------------------------------------------------------------------
      # Source selection (lib.fileset)
      #
      #   * all *.org files anywhere in the repo (the org-roam notes)
      #   * the LICENSES/ tree, so the built artifacts remain license-complete
      #     under REUSE
      #
      # Everything else (npins/, *.nix, org2zola.py, REUSE.toml, ...) is
      # excluded on purpose: editing them never triggers a site rebuild.
      # Note that org2zola.py itself still hashes into the derivation via
      # site.nix (${./org2zola.py}), so converter changes DO rebuild.
      # ------------------------------------------------------------------------
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
      forAllSystems = lib.genAttrs systems;
    in
    {
      # ----------------------------------------------------------------------
      # Packages — the deployable site
      # ----------------------------------------------------------------------
      packages = forAllSystems (
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

      # ----------------------------------------------------------------------
      # Dev shell — live preview & license hygiene
      #
      #   serve             convert notes + live preview on http://127.0.0.1:3000
      #   regenerate-site   re-run the org -> markdown conversion only
      #   reuse lint        check REUSE compliance of the repo
      # ----------------------------------------------------------------------
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          regenerate = pkgs.writeShellScriptBin "regenerate-site" ''
            set -euo pipefail
            SRC="''${1:-$ORG_SRC:-$PWD}"
            SITE="''${SITE:-$SRC/site-src}"
            python3 ${./org2zola.py} "$SRC" "$SITE" "http://127.0.0.1:3000/"
          '';

          # One command: convert notes, then serve with live reload.
          serve = pkgs.writeShellScriptBin "serve" ''
            set -euo pipefail
            SRC="''${ORG_SRC:-$PWD}"
            SITE="$SRC/site-src"
            python3 ${./org2zola.py} "$SRC" "$SITE" "http://127.0.0.1:3000/"
            cd "$SITE"
            exec zola serve
          '';
        in
        {
          default = pkgs.mkShell {
            packages = [
              # site toolchain
              pkgs.zola
              pkgs.pandoc
              pkgs.python3
              # helpers
              regenerate
              serve
              # license compliance
              pkgs.reuse
            ];

            shellHook = ''
              echo "Site dev shell:"
              echo "  serve              convert + live preview on http://127.0.0.1:3000"
              echo "  regenerate-site    re-run org -> markdown conversion only"
              echo "  reuse lint         check REUSE compliance"
            '';
          };
        }
      );
    };
}

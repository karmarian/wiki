# SPDX-FileCopyrightText: 2026 karmar <karmar@posteo.de>
# SPDX-License-Identifier: GPL-3.0-or-later

# ============================================================================
# site.nix — build a Zola static site from the org-roam notes of
#            https://gitlab.com/karmarian/wiki
#
# Pipeline (implemented by org2zola.py next to this file):
#     org-roam notes
#       -> resolve [[id:...]] roam links via the :ID: property drawers
#       -> pandoc (org -> gfm) per file
#       -> Zola front matter (title from #+title:, date from filename)
#       -> zola build
#
# Build:    nix build .#default
# Output:   result/ — the finished "public/" directory, ready to deploy.
#
# The same org2zola.py is used by the flake's devShell (`nix develop`,
# `regenerate-site`) so the live preview and the production build can
# never drift apart.
#
# NOTE: cacert + SSL_CERT_FILE are required because Zola sets up a reqwest
# HTTPS client during `zola build` even when no template loads remote
# data; without CA certificates in the Nix sandbox it panics with
# "No CA certificates were loaded from the system".
# ============================================================================

{
  lib,
  stdenv,
  zola,
  pandoc,
  python3,
  cacert,
  src,
  baseUrl ? "https://karmarian.gitlab.io/wiki/",
}:

stdenv.mkDerivation {
  pname = "wiki-site";
  version = "0.1.0";

  inherit src;

  nativeBuildInputs = [
    zola
    pandoc
    python3
    cacert
  ];

  # Zola's embedded reqwest HTTPS client needs a CA bundle; the Nix build
  # sandbox ships none. reqwest honours SSL_CERT_FILE.
  SSL_CERT_FILE = "${cacert}/etc/ssl/certs/ca-bundle.crt";

  buildPhase = ''
    runHook preBuild
    site=$NIX_BUILD_TOP/site
    python3 ${./org2zola.py} "$src" "$site" "${baseUrl}"
    (
      cd "$site"
      zola build --output-dir "$out"
    )
    runHook postBuild
  '';

  dontInstall = true;

  meta = with lib; {
    description = "Zola static site built from the karmarian/wiki org-roam notes";
    platforms = platforms.unix;
  };
}

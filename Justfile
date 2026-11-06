#SPDX-FileCopyrightText: 2026 karmar <karmar@posteo.de>
#SPDX-License-Identifier: CC0-1.0

# karmarian/wiki — org-roam notes -> Zola static site
#
# Run `just -l` for this list of recipes (doc comments below are the
# single source of truth for the dev workflow).
#
# Variables:
#   ORG_SRC  source dir with the *.org notes (default: the repo root)
#   SITE     output dir for the site skeleton (default: $ORG_SRC/site-src)

src := env_var_or_default("ORG_SRC", justfile_directory())
site := src + "/site-src"

alias r := regenerate-site
alias s := serve
alias i := init

# Re-run the org-roam -> markdown conversion only
# Use this while editing notes when `just serve` is already running in
# another terminal: Zola picks up the changed .md and live-reloads.
regenerate-site:
    python3 org2zola.py "{{src}}" "{{site}}" "http://127.0.0.1:3000/"

# Convert notes, then serve with live reload on http://127.0.0.1:3000
serve: regenerate-site
    cd "{{site}}" && exec zola serve

# Check for the required tools and print install hints for your platform
# (users on the Nix devShell already have everything; this is for others)
init:
    #!/usr/bin/env bash
    set -euo pipefail
    ok=1
    for tool in python3 pandoc zola; do
      if command -v "$tool" >/dev/null 2>&1; then
        echo "  ok    $tool ($(command -v "$tool"))"
      else
        echo "  MISS  $tool"
        ok=0
      fi
    done
    if [ "$ok" -eq 1 ]; then
      echo "All tools present — run \`just serve\` for a live preview."
      exit 0
    fi
    echo
    echo "Install the missing tools:"
    if command -v apt-get >/dev/null 2>&1; then
      echo "  sudo apt-get install python3 pandoc"
      echo "  zola: https://www.getzola.org/documentation/installation/"
    elif command -v dnf >/dev/null 2>&1; then
      echo "  sudo dnf install python3 pandoc"
      echo "  zola: https://www.getzola.org/documentation/installation/"
    elif command -v pacman >/dev/null 2>&1; then
      echo "  sudo pacman -S python pandoc zola"
    elif command -v apk >/dev/null 2>&1; then
      echo "  sudo apk add python3 pandoc zola"
    elif command -v brew >/dev/null 2>&1; then
      echo "  brew install python pandoc zola"
    else
      echo "  python3, pandoc, zola — see your distribution's packages"
    fi
    exit 1

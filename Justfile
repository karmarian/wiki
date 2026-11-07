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
#   FTP_HOST webhost FTP server for `just deploy` — REQUIRED, no default;
#            the hoster's actual FTP address (check the provider panel),
#            NOT necessarily the website domain.
#   FTP_USER explicit FTP username; if unset, credentials are read from
#            ~/.netrc (machine must match FTP_HOST, mode 600) and lftp
#            prompts for the password interactively if no entry matches.
#
# org2zola.py assumes an empty SITE_DIR: recipes below remove it first,
# so stale files from previous runs can never leak into the build.

src := env_var_or_default("ORG_SRC", justfile_directory())
site := src + "/site-src"

alias r := regenerate-site
alias s := serve
alias i := init
alias d := deploy

# Re-run the org-roam -> markdown conversion only (wipes site-src first)
# Use this while editing notes when `just serve` is already running in
# another terminal: Zola picks up the changed .md and live-reloads.
regenerate-site:
    rm -rf "{{site}}"
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

# Build the site and mirror it to the webhost via FTP
# Credentials come from ~/.netrc (machine matching FTP_HOST) or an
# interactive password prompt (set FTP_USER to force the prompt).
# NOTE: --no-preserve=mode is essential — the Nix store output is
# read-only, and uploading those permission bits would make the remote
# files undeletable/unoverwritable.
deploy:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v lftp >/dev/null 2>&1 || { echo "MISS lftp — install it first"; exit 1; }
    host="${FTP_HOST:-}"
    user="${FTP_USER:-}"
    if [ -z "$host" ]; then
        echo "FTP_HOST is not set."
        echo "Set it to your webhost's actual FTP server (see the provider"
        echo "control panel — it is not necessarily the website domain):"
        echo
        echo "  FTP_HOST=<ftp-server> just deploy"
        exit 1
    fi
    nix build .#default
    rm -rf .deploy && mkdir .deploy
    cp -rL --no-preserve=mode result/. .deploy/
    chmod -R u+w .deploy
    if [ -n "$user" ]; then
        # explicit user, no stored password: lftp prompts interactively
        lftp -u "$user" -e 'mirror -P 10 -R --delete .deploy public_html; bye' "$host"
    else
        # credentials via ~/.netrc (machine must equal FTP_HOST)
        lftp -e 'mirror -P 10 -R --delete .deploy public_html; bye' "$host"
    fi
SPDX-FileCopyrightText: 2026 karmar <karmar@posteo.de>

SPDX-License-Identifier: CC-BY-SA-4.0

# KARMAR — org-roam wiki and blog

## Description
Personal wiki and blog written as org-roam notes.
The notes live in one flat pool, linked by org-roam IDs; notes tagged
`:blog:` are published as blog articles, everything else as wiki pages.
The static website is built from the notes with Zola and deployed to
[karmar.org](https://karmar.org).

## Usage

### Build the website
Build the deployable site artifacts:
```shell
nix build .#default
```
The resulting `result/` directory contains the static site ready for
deployment.

### Local development
Enter the development shell and list the recipes:
```shell
nix develop
just -l
```
Convert the notes and serve the site with live reload:
```shell
just serve
```
While the server is running, re-run the conversion after editing notes:
```shell
just regenerate-site
```
Users outside the Nix devShell can check the required tools with
`just init`.

### Deployment
Deploy the site to the webhost via FTP:
```shell
just deploy
```
The recipe builds the site, copies it to `.deploy/` with writable
permissions (the Nix store output is read-only) and mirrors it to the
`public_html` directory of the webhost.
The target host defaults to `ftp.karmar.org` and can be overridden with
`FTP_HOST=<host> just deploy`.
lftp reads the FTP credentials from `~/.netrc` (machine, login,
password) or prompts for the password interactively if none is stored:
```
machine ftp.karmar.org
login <user>
password <secret>
```
Note that `~/.netrc` must contain the host as given by `FTP_HOST`.
The production `base_url` is set in `flake.nix` (`baseUrl` argument) and
must match the deployed domain.

### Writing notes
Notes are plain `.org` files with org-roam `:ID:` drawers; roam links
between notes are resolved to website links at build time.
Tag a note with `#+filetags: :blog:` to publish it as a blog article,
otherwise it appears in the wiki section.
Articles with `#+language: de` that link to their English counterpart
(via a roam link between two blog notes) are published as translations
with a language-switch button.

## AI assistance
The wiki notes are written mainly without AI assistance, unless noted
otherwise in the respective note.
The website tooling (Python converter, Nix derivations, Justfile) was
developed with AI coding assistance and reviewed by the author.

## Authors
**karmar@posteo.de**

## License
This repository uses [REUSE](https://reuse.software/) to provide license
information in an unambiguous and convenient way.
Take a look at the header of the file of interest or in the
[LICENSES](/LICENSES/) folder.
To check REUSE compliance run:
```shell
nix develop
reuse lint
```
The licensing follows the content/code distinction:

- **CC-BY-SA-4.0** — the wiki and blog notes (`*.org`) and this README:
  copyleft for prose, compatible with the code license below.
- **GPL-3.0-or-later** — the website tooling (`org2zola.py`,
  `site.nix`, `flake.nix`): copyleft where it matters for software;
  GPL instead of AGPL, as this tooling is not offered as a network
  service.
- **CC0-1.0** — trivial glue and metadata without creative content
  (`Justfile`, `.gitignore`): maximum reuse, no restrictions.

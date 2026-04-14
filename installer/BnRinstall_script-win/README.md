# OpenShot BnR 1.0.1

**OpenShot BnR** is a Windows-first bootstrap, build, and launch helper for **OpenShot** source builds.

This pass is shaped to read more like a practical contribution around OpenShot and less like a standalone product bundle. The main job is simple: **get OpenShot working on a stock or half-broken Windows machine with fewer mystery failures**.

## How this differs from OpenShot's existing installer

OpenShot already has official installer and packaging infrastructure in its upstream `installer/` directory. That tooling is aimed at **packaging and shipping OpenShot builds**.

OpenShot BnR aims at a different problem: **bootstrapping a real Windows machine from zero to a working source build**.

| Tooling | Primary job |
|---|---|
| OpenShot upstream installer/build scripts | Package, launch, and release finished OpenShot builds |
| OpenShot BnR | Restore prerequisites, clone/update repos, build native dependencies, verify bindings, and generate launch helpers on stock Windows |

So this helper is best described as a **Windows bootstrap and diagnostics helper**. It supports the upstream project workflow, but it does not try to replace the project's official installer or release pipeline.

## Upstream context

OpenShot itself is the work of the **OpenShot project and contributors**.

- OpenShot website: https://www.openshot.org/
- OpenShot source repository: https://github.com/OpenShot/openshot-qt
- OpenShot developer docs: https://www.openshot.org/static/files/user-guide/developers.html
- OpenShot contribution guide: https://github.com/OpenShot/openshot-qt/blob/develop/CONTRIBUTING.md

This helper sits beside that work. Its job is the painful part on a fresh or half-broken Windows machine: verifying prerequisites, restoring toolchain pieces, building dependencies in the right order, checking bindings honestly, and leaving behind logs and launch helpers that are readable.

## What this helper does

- checks elevation, WinGet, Git, and MSYS2
- refreshes MSYS2 and resolves live UCRT64 dependency choices
- clones or updates:
  - `libopenshot-audio`
  - `libopenshot`
  - `openshot-qt`
- builds the native stack in order
- verifies Python bindings in installed and source-build modes
- repairs the runtime launch path
- generates launcher plus portable and frozen helper files
- exposes docs and debug output from the command line

## Why it may still be useful

The upstream installer helps ship OpenShot. This helper helps **prepare the machine, build the native stack, and prove that the source build actually launches**.

That makes it more of a **bootstrap and diagnostics helper** than a replacement installer.

## Quick start

```bash
py -3 OpenShot_BnR_v1_0.py
```

After a successful run:

```bash
cmd /c "C:\OpenShotBuild\Launch-OpenShot-Qt.cmd"
py -3 "C:\OpenShotBuild\Launch-OpenShot-Qt.py"
```

## Information commands

```bash
py -3 OpenShot_BnR_v1_0.py --usage
py -3 OpenShot_BnR_v1_0.py --help
py -3 OpenShot_BnR_v1_0.py --about
py -3 OpenShot_BnR_v1_0.py --version
py -3 OpenShot_BnR_v1_0.py --docs
py -3 OpenShot_BnR_v1_0.py --install
py -3 OpenShot_BnR_v1_0.py --manual-install
py -3 OpenShot_BnR_v1_0.py --log-guide
py -3 OpenShot_BnR_v1_0.py --troubleshoot
py -3 OpenShot_BnR_v1_0.py --release-guide
py -3 OpenShot_BnR_v1_0.py --debug
```

## Docs included

- [INSTALL.md](INSTALL.md) — install flow and result reading
- [MANUAL_INSTALL.md](MANUAL_INSTALL.md) — manual dependency references and upstream links
- [LOG_GUIDE.md](LOG_GUIDE.md) — successful log walkthrough
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common failure paths and fixes
- [RELEASE_GUIDE.md](RELEASE_GUIDE.md) — release and review checklist
- [help.html](help.html) — local browser help page

## OpenShot submission notes

To align with the OpenShot contribution workflow, this helper is shaped as a **source-build bootstrap contribution**, not a replacement for the official installer.

- branch from `develop`
- open a pull request against `develop`
- draft / WIP pull requests are acceptable when feedback is needed early
- the PR description should clearly explain the problem and the solution
- if reporting a bug instead of submitting code, include the operating system and attach relevant log files

The cleanest framing is: **make OpenShot easier to build and launch from source on stock Windows**.

## Contribution-shaped trim

This pass removes a lot of the stuff that made the package feel more like a side product than an upstream-friendly helper:

- no personal photos
- no decorative mascot assets
- no `.url` shortcuts
- no vendored jQuery source tree
- less self-promotional copy
- more direct attribution to OpenShot and its upstream repos

## Links

- BnR contribution repo: https://github.com/tibberous/BnRinstall_script-win
- OpenShot repo: https://github.com/OpenShot/openshot-qt
- OpenShot docs: https://www.openshot.org/static/files/user-guide/developers.html
- Author: https://www.trentontompkins.com

For a free consultation about Windows/OpenShot build automation: **(724) 431-5207** • **trenttompkins@gmail.com**

*Coded with ❤️ with ChatGPT.*

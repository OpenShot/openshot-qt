# RELEASE_GUIDE.md

## Purpose

This checklist is for packaging this helper as a clean OpenShot contribution instead of a standalone side product.

## Best upstream framing

Describe the helper as:

> a Windows bootstrap/build helper for OpenShot source builds on stock or partially configured Windows systems

Do **not** describe it as a replacement for OpenShot's existing installer. The upstream installer and packaging scripts are for shipping finished builds. This helper is for restoring prerequisites, building dependencies, verifying bindings, and leaving behind readable launch helpers and logs.

## OpenShot pull request checklist

- branch from `develop`
- open the PR against `develop`
- explain the problem and the solution clearly
- mention how this differs from the upstream installer
- keep the work focused on OpenShot use, not personal branding
- use draft / WIP status if review or additional testing is still needed

## Bug report / issue checklist

If opening an issue instead of a PR:

- search existing issues first
- include the operating system
- include clear reproduction steps
- attach the relevant log files

On Windows, OpenShot log files are typically found in:

- `%USERPROFILE%\.openshot_qt\openshot-qt.log`
- `%USERPROFILE%\.openshot_qt\libopenshot.log`

## Local quality pass

- `py -3 OpenShot_BnR_v1_0.py --help` runs cleanly
- `py -3 OpenShot_BnR_v1_0.py --about` runs cleanly
- `py -3 OpenShot_BnR_v1_0.py --version` runs cleanly
- `py -3 OpenShot_BnR_v1_0.py --debug` runs cleanly
- `help.html` opens without broken local assets
- no dead local file references remain in docs

## Submission note

The clearest summary is: this helper makes it easier to get OpenShot running from source on stock Windows.

# CONTRIBUTING.md

This helper is intended to fit into the OpenShot contribution workflow. The upstream OpenShot rules are the primary guide:

- OpenShot repository: https://github.com/OpenShot/openshot-qt
- OpenShot contributing guide: https://github.com/OpenShot/openshot-qt/blob/develop/CONTRIBUTING.md

## Recommended flow

1. Branch from `develop`.
2. Keep the changes focused and explain the problem clearly.
3. Open a pull request against `develop`.
4. Use draft / WIP status if the work still needs feedback or testing.

## For this helper specifically

The cleanest framing is that this is a Windows bootstrap/build helper for source builds. It supports the OpenShot workflow, but it does not replace the official packaging installer.

When reporting bugs or requesting feedback, include the OS and attach relevant log files.

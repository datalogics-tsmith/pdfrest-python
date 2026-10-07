# Vendored quality tooling

This directory contains vendored contributor tooling, separate from project
source. The tooling is maintained and tested upstream. Executing the local copy
requires no GitHub authentication or access to its maintained source.

## Copy identity

- Installed file: `.cit-quality/vendor/check_nfc_filenames.py`.
- Installed SHA-256:
  `83d3bb79ebf3a5d6cb4f213f3af4421bd258693057514637ce87f3fc00a79056`.

The checksum identifies the installed bytes; it is not evidence of a passing
upstream test run.

## Review and updates

Local review covers the copied artifact's identity, updates, public
documentation, and integration with the repository's pre-commit hook.
Implementation review and implementation tests belong upstream. This repository
does not maintain duplicate implementation tests for the vendored checker.

Preserve the copied bytes. Contribute implementation fixes to the maintained
source, then update the vendored copy and its checksum together. Local behavior
changes would require normal implementation review and regression coverage. Keep
the vendored directory out of project source, test discovery, coverage, and
distribution inputs where those tools would otherwise traverse it.

The `linguist-vendored` attribute identifies the review boundary. Hook
integration and public documentation remain subject to repository review.

## Run the installed hook

From the repository root:

```shell
uvx --from pre-commit==4.6.2 pre-commit run check-nfc-filenames --all-files
```

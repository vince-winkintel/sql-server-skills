# Go sqlcmd compatibility audit — unreleased candidate

Prepared 2026-11-18; source and initialization/dispatch review updated 2026-11-19.
This is an unreleased documentation candidate, not a package version or publication
record. Releases remain identified by Git tags; no VERSION manifest is used.
Existing DMV workflows retain their client requirements. Optional features carry
their real compatibility minima inline in the root and diagnostics skills.

## Immutable upstream provenance

- Microsoft Go sqlcmd v1.10.0 → v1.11.0.
- [Authoritative v1.11.0 release](https://github.com/microsoft/go-sqlcmd/releases/tag/v1.11.0).
- Exact source commit: `a97013a80b01f3aaac4fb17e9ef422283f15cb2f`.
- [Pinned change history](https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/CHANGELOG.md).
- Guidance is authored from source, not captured CLI help. The retained release
  snapshot contained no assets; no upstream binary/help capture or build is claimed.

## Reviewed behavior

Go sqlcmd 1.11.0 introduces ASCII tables and raw error-prefix preservation, changes
`-G` without `-U` to ActiveDirectoryDefault, validates YAML filename suffixes, and
fixes password/token propagation for ActiveDirectoryServicePrincipalAccessToken.
That token fix does not redact connection URLs. `-F` remains a certificate hostname.
Delimiter output does not provide quoted/escaped CSV.

Legacy startup initializes credentials before parsing `-U`; exporting SQLCMDUSER
with the selected login prevents a current basic-auth context from replacing an
operator-provisioned SQLCMDPASSWORD. Missing passwords still stop before transport.
The modern subcommand CLI alone registers `--sqlconfig`; the legacy query examples
must not use it. Dotfile `.sqlconfig` has a rejected suffix. ASCII output buffers
rows, ignores `-y`/`-Y`/`-h`, and can truncate cells even when output goes to a file.

Exact source anchors at the commit above:

| Behavior | Source |
|---|---|
| CLI selection, legacy environment initialization | `cmd/modern/main.go:40–100,105–136` |
| Subcommand recognition and config flag | `internal/cmdparser/cmd.go:183–209`; `cmd/modern/root.go:120–125` |
| Authentication selection and password consumption | `cmd/sqlcmd/sqlcmd.go:203–221,744–765` |
| Optional output flags | `cmd/sqlcmd/sqlcmd.go:486–495` |
| Filename suffix validation | `internal/config/config.go:25–38` |
| ASCII buffering, width limits and truncation | `pkg/sqlcmd/format_ascii.go:43–94,171–195`; `README.md:186` |
| Token/password propagation | `pkg/sqlcmd/connect.go:87–95,128–129` |

Azure SQL Edge removal does not alter these diagnostics: this package did not
claim Edge provisioning support. Devcontainer, dependencies/toolchain, translations,
CI/release infrastructure and empty-argument fixes require no new diagnostic workflow.

## Packaging and validation boundaries

The canonical merged ZIP still contains one SKILL.md and omits references and SQL
scripts. Authentication and output-safety essentials remain inline. Manual installs
retain references for additional detail. Root and diagnostics keep the new
authentication/output prerequisites inline. Existing module safety/attribution
content is unchanged; this audit remains in export-ignored `docs/`.

Offline checks use synthetic credentials and recording sqlcmd stubs, including a
model of the documented context-precedence branch. They exercise authored shell
examples and package contents; they do not execute Go sqlcmd or SQL Server, verify
Azure identity behavior, or establish real formatter/server results. No live database
operations, real credentials, global configuration or user installations are used.

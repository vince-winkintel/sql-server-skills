# Go sqlcmd for operator-run diagnostics

This reference is self-contained when installed with `sqlserver-diagnostics/`.
Identify the installed client as Go sqlcmd or ODBC sqlcmd before choosing flags;
the names are shared, but their option sets differ. Existing DMV workflows do not
gain a new minimum client version. The optional ASCII formatter and raw-error
flag described here require **Go sqlcmd 1.11.0 or later**.

## Read a small diagnostic result

Use an operator-selected server and identity with permission to read the target
DMV (`VIEW SERVER STATE`, or the applicable permission on the target server).
In Bash, select exactly one setup in the same session as the query:

```bash
# Integrated authentication with an operator-configured identity
SQL_AUTH=(-E)
```

```bash
# SQL authentication: SQLCMDPASSWORD must already be securely exported
[ -n "${SQLCMDPASSWORD:-}" ] || { echo 'SQLCMDPASSWORD not provisioned or empty' >&2; exit 1; }
SQL_AUTH=(-U "${SQL_USER:?Set the operator-selected SQL login}")
```

sqlcmd reads `SQLCMDPASSWORD` directly. Never ask for, print, expand into arguments,
or persist passwords or tokens. Do not create password files, enable shell tracing,
or dump the environment. If secure authentication is unavailable, stop for the
operator to configure it outside the agent. A missing SQL password must never
trigger an identity fallback. Recheck its presence if the environment changes.

```bash
# Read-only query; no repository SQL script is needed
sqlcmd -S "${SQL_SERVER:?Set the operator-selected server}" "${SQL_AUTH[@]:?Select authentication first}" -d master -Q "SELECT TOP (5) wait_type, wait_time_ms FROM sys.dm_os_wait_stats ORDER BY wait_time_ms DESC;" -b --ascii
```

Check the exit status; on error, discard partial output and investigate before
using the result. This query is a small cumulative wait snapshot, not a diagnosis
on its own. ASCII tables buffer result rows; use bounded results for inspection.

`--ascii` selects the table formatter; `-v SQLCMDFORMAT=ascii` is the source-documented
alternative. Do not combine `--ascii` with `--vertical`. Uppercase `-F` takes a
certificate hostname (`--host-name-in-certificate`), not a format name. Lowercase
`-f` is not registered by the reviewed Go query parser; do not substitute it or
borrow ODBC flags. Flag case matters. [Parser and flag definitions][parser],
[format selection and buffering][ascii], [upstream usage][readme].

For delimiter output, `-s ","` sets a column separator and `-W` removes trailing
spaces. This does not quote or escape CSV fields: data can contain commas and
newlines. Use a suitable export tool when a downstream consumer requires CSV.
[Separator and trim flags][parser], [default formatter][formatter].

## Error messages

Go sqlcmd 1.11.0 adds `-j` / `--raw-errors`. It preserves the `mssql: ` prefix in
SQL Server error text instead of replacing it with the message alone. Existing
error headers, severity filtering and output routing still apply; it is not a
request to reveal secrets or a redaction control. Use it only when a diagnostic
consumer needs that prefix. Keep passwords, tokens and connection URLs out of
shared logs, with or without this option. [Flag definition][parser],
[error formatter][formatter].

## Configuration and identity selection

- `--sqlconfig` selects a Go sqlcmd configuration file containing YAML. Use `.yaml`
  or `.yml` for an explicit suffix; other suffixes are rejected beginning with
  Go sqlcmd 1.11.0. Extensionless paths remain supported, including the default
  configuration name. Suffix checking is case-insensitive. Do not print config
  contents to troubleshoot this check. [Config flag][config-flag],
  [extension validation][config].
- Beginning with Go sqlcmd 1.11.0, `-G` without a username selects
  `ActiveDirectoryDefault`, which walks an Azure credential chain, rather than
  `ActiveDirectoryIntegrated`. Use it only after the operator explicitly chooses
  that authentication flow and verifies the intended identity. Do not add `-G`
  to the integrated or SQL-authentication examples above, or use it to recover
  from missing credentials. `--authentication-method` is a separate explicit
  selection and cannot be combined with `-G`. [Authentication selection][parser].
- The Go sqlcmd 1.11.0 fix for `ActiveDirectoryServicePrincipalAccessToken` marks
  that method as requiring a password/token and includes it in the internal
  connection URL. It fixes missing credential propagation; it does **not** remove
  secrets from URLs or guarantee redaction. Keep the same password/token
  nonexposure rules and operator-controlled provisioning. [Connection handling][connect].

## Source provenance and validation limits

The guidance above was checked against Microsoft's Go sqlcmd v1.11.0 source at
commit `a97013a80b01f3aaac4fb17e9ef422283f15cb2f`; all links below pin that commit.
It is source-backed guidance, not captured help or observed binary behavior.
The official release snapshot contained no assets. No upstream binary was built
or executed, and no sqlcmd or SQL Server runtime validation was performed.

[parser]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/cmd/sqlcmd/sqlcmd.go
[ascii]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/pkg/sqlcmd/format_ascii.go
[formatter]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/pkg/sqlcmd/format.go
[readme]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/README.md
[config-flag]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/cmd/modern/root.go
[config]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/internal/config/config.go
[connect]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/pkg/sqlcmd/connect.go

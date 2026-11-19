# Go sqlcmd for operator-run diagnostics

This reference is self-contained when installed with `sqlserver-diagnostics/`.
Identify the installed client as Go sqlcmd or ODBC sqlcmd before choosing flags;
the names are shared, but their option sets differ. Existing DMV workflows do not
gain a new minimum client version. The optional ASCII formatter and raw-error
flag described here require **Go sqlcmd 1.11.0 or later**.

## Read a small connection result

Use an operator-selected server and identity with permission to connect to `master`.
This formatter demonstration returns the current session ID; it does not diagnose
waits. Actual DMV queries require their own target/version-specific permissions.
In Bash, select exactly one setup in the same session as the query:

```bash
# Integrated authentication with an operator-configured identity
SQL_AUTH=(-E)
```

```bash
# SQL authentication: SQLCMDPASSWORD must already be securely exported
[ -n "${SQLCMDPASSWORD:-}" ] || { echo 'SQLCMDPASSWORD not provisioned or empty' >&2; exit 1; }
export SQLCMDUSER="${SQL_USER:?Set the operator-selected SQL login}"
SQL_AUTH=(-U "$SQLCMDUSER")
```

Go sqlcmd initializes legacy invocations from `~/.sqlcmd/sqlconfig` before parsing
`-U`. A current context with a nonempty basic-auth username and password can
overwrite `SQLCMDPASSWORD` when `SQLCMDUSER` is empty. Export the operator-selected
login as `SQLCMDUSER` as above to prevent that replacement; `-U` alone does not.
Do not read, print or change stored credentials to work around this precedence.
[Legacy initialization][initialization], [password consumption][parser].

Never ask for, print, expand into arguments, or persist passwords or tokens. Do not create password files, enable shell tracing,
or dump the environment. If secure authentication is unavailable, stop for the
operator to configure it outside the agent. A missing SQL password must never
trigger an identity fallback. Re-run the setup if the environment changes.

```bash
# Read-only query; no repository SQL script is needed
sqlcmd -S "${SQL_SERVER:?Set the operator-selected server}" "${SQL_AUTH[@]:?Select authentication first}" -d master -Q "SELECT @@SPID AS session_id;" -b -w 80 --ascii
```

Check the exit status; on error, discard partial output and investigate before
using the result. For wait analysis, use the filtered inline query in the diagnostics
skill or `scripts/wait-stats.sql` from the repository; unfiltered top waits can be
dominated by benign background activity.

ASCII tables buffer result rows and can silently truncate wide cells with `...`
(very narrow cells are cut without the marker). Use only small, narrow results,
never query text, XML plans or generated DDL. `-y`, `-Y` and `-h` (the variables
`SQLCMDMAXVARTYPEWIDTH`, `SQLCMDMAXFIXEDTYPEWIDTH`, `SQLCMDHEADERS`) are ignored.
`-w` / `SQLCMDCOLWIDTH` sets the width; with no positive width, stdout's terminal
width is used even when `-o file` redirects results. Without a terminal, the source
uses a large finite fallback. Columns can split into separate table segments;
individual cells are still capped. Increasing `-w` does not guarantee full values.
Keep the default formatter and `-y 0 -w 65535` for missing-index reports; do not
add `--ascii`. [Column caps and truncation][ascii], [ignored variables][readme].

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

- `--sqlconfig` belongs to the modern subcommand CLI: the first argument must
  select that CLI (for example `sqlcmd config` or `sqlcmd query`), with the flag
  after the subcommand. It is not registered on the legacy query parser; do not
  combine it with the `sqlcmd -S ... -Q/-i` invocations used here. Legacy startup
  checks the default `~/.sqlcmd/sqlconfig` instead. [CLI dispatch][initialization],
  [subcommand recognition][dispatch], [config flag][config-flag].
- The configuration file contains YAML. Use `.yaml`
  or `.yml` for an explicit suffix; other suffixes are rejected beginning with
  Go sqlcmd 1.11.0. Suffix-free basenames such as `sqlconfig` remain supported,
  including the default name. A dotfile basename such as `.sqlconfig` has the
  suffix `.sqlconfig` and is rejected. Suffix checking is case-insensitive. Do not
  print config contents to troubleshoot this check. [Config flag][config-flag],
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
[initialization]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/cmd/modern/main.go#L40-L136
[dispatch]: https://github.com/microsoft/go-sqlcmd/blob/a97013a80b01f3aaac4fb17e9ef422283f15cb2f/internal/cmdparser/cmd.go#L183-L209

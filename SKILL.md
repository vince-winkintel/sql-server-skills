---
name: sql-server-skills
description: "Comprehensive SQL Server performance diagnostics, index analysis, execution plan interpretation, query optimization, schema management, backup/restore, and monitoring using sqlcmd and T-SQL DMVs. Use when analyzing slow queries, investigating wait stats, finding missing indexes, reading execution plans, optimizing stored procedures or views, managing migrations, monitoring SQL Agent jobs, or diagnosing blocking/deadlocks on Microsoft SQL Server. Triggers on: SQL Server, MSSQL, sqlcmd, T-SQL performance, slow query, execution plan, DMV, missing index, wait stats, blocking, deadlock, stored procedure optimization, view tuning."
openclaw:
  requires:
    credentials:
      - name: SQL_SERVER
        description: >
          SQL Server hostname or instance (e.g. myserver\SQLINSTANCE or 10.0.0.1).
          Used as the sqlcmd -S argument. Required for all script execution.
        required: true
      - name: SQL_USER
        description: >
          SQL authentication login name for sqlcmd -U flag.
          Not required when using Windows Authentication (-E flag).
        required: false
        fallback: Integrated authentication (sqlcmd -E, no SQL password required)
      - name: SQLCMDPASSWORD
        description: >
          SQL authentication password read directly by sqlcmd from the environment.
          Not required when using Windows Authentication (-E flag).
          Must already be securely provisioned by the operator. Never ask for, print,
          or persist this value, including in skill files, shell history or logs.
        required: false
        fallback: Integrated authentication (sqlcmd -E, no SQL password required)
    network:
      - description: >
          Outbound TCP to SQL Server on port 1433 (default) or a configured custom port.
          All diagnostic DMV scripts are read-only SELECT statements.
          No data is sent to any third party; all traffic is SQL Server TDS protocol
          between the agent host and your SQL Server instance.
        scope: authenticated SQL connections to your SQL Server only
    write_access:
      - description: >
          ALTER INDEX statements in sqlserver-indexes/SKILL.md modify index structures.
          DDL statements in sqlserver-schema/SKILL.md modify database schema.
          Backup/restore, statistics updates and cache operations also have
          operational impact; require exact-target DBA review, least privilege,
          staging validation and a tested recovery plan before changes.
          The KILL command referenced in blocking-analysis.sql and
          sqlserver-monitoring/SKILL.md is explicitly commented out and must
          never be executed by agents or automated processes, even with approval.
          Only a human DBA issues KILL after confirming rollback safety with the application owner.
---

# SQL Server Skills

Comprehensive SQL Server skill for AI agents. Covers performance diagnostics, index analysis, execution plan interpretation, query optimization, schema management, backup/restore, and monitoring — all via `sqlcmd` and T-SQL DMVs.

---

## Requirements

- **`sqlcmd`** — [Microsoft Download](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility)
- **SQL Server 2016+** — All DMV queries target compatibility level 130+
- **Permissions** — `VIEW SERVER STATE` for most DMV queries; operation-specific least privilege and exact-target DBA review for changes

---

## Quick Connect

Prefer integrated authentication (`-E`) with an operator-configured identity. For SQL
authentication, sqlcmd reads an already securely provisioned `SQLCMDPASSWORD` directly;
never expand it into arguments. Never ask for, print, or persist passwords. Do not
create password files, use shell tracing, or dump the environment. If no secure
authentication is available, stop and let the operator configure it outside the agent.

Choose exactly one authentication setup in the same Bash session as the workflows.
The choice is explicit: a missing SQL password never falls back to another identity.

```bash
# Integrated authentication: operator-configured identity
SQL_AUTH=(-E)
```

```bash
# SQL Authentication: SQLCMDPASSWORD must already be exported securely
[ -n "${SQLCMDPASSWORD:-}" ] || { echo 'SQLCMDPASSWORD not provisioned or empty' >&2; exit 1; }
SQL_AUTH=(-U "$SQL_USER")
```

```bash
# Connect to the selected database using the chosen authentication
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d "$SQL_DATABASE"

# Run a diagnostic script
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/top-slow-queries.sql

# Run with output to file
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/wait-stats.sql -o results.txt -s "," -W
```

SQL authentication requires a nonempty, exported `SQLCMDPASSWORD` provisioned outside
this agent session. If it is absent or empty, stop; never type a password into a prompt.
Re-run the presence check before SQL-auth workflows if the environment has changed.

### Compatibility

The old `SQL_PASSWORD` credential name is replaced by `SQLCMDPASSWORD`. Operators must
update secure environment provisioning outside the agent; the old variable is not read
or copied. This is a breaking credential-name change. Integrated authentication needs
no SQL password. The examples below reuse the chosen `SQL_AUTH` Bash array for either
mode; do not switch identities silently.

---

## Skill Organization

| Sub-Skill | Path | Use When |
|-----------|------|----------|
| **Diagnostics** | `sqlserver-diagnostics/SKILL.md` | Server is slow — find the bottleneck (wait stats, slow queries, active requests) |
| **Indexes** | `sqlserver-indexes/SKILL.md` | Find missing indexes, fix fragmentation, drop unused indexes |
| **Execution Plans** | `sqlserver-execution-plans/SKILL.md` | Read and interpret query execution plans, spot bad operators |
| **Query Optimization** | `sqlserver-query-optimization/SKILL.md` | Fix stored procedures, views, anti-patterns, parameter sniffing |
| **Schema** | `sqlserver-schema/SKILL.md` | CREATE/ALTER TABLE, migrations, constraints, data types |
| **Backup/Restore** | `sqlserver-backup/SKILL.md` | BACKUP DATABASE, RESTORE, check backup history |
| **Monitoring** | `sqlserver-monitoring/SKILL.md` | SQL Agent jobs, error log, blocking, deadlocks, long-running transactions |

---

## Decision Tree — What Are You Trying To Do?

```
Is the server slow or a query timing out?
├── I don't know WHERE the bottleneck is → sqlserver-diagnostics
│   └── Start with wait-stats.sql, then top-slow-queries.sql
│
├── I have a specific slow query → sqlserver-execution-plans
│   └── Capture the plan, identify bad operators
│
├── I suspect missing or broken indexes → sqlserver-indexes
│   └── Run missing-indexes.sql + index-fragmentation.sql
│
└── I want to rewrite/fix bad T-SQL code → sqlserver-query-optimization
    └── Check anti-patterns: cursors, non-SARGable, DELETE+INSERT loops

Is there a blocking/locking issue?
└── sqlserver-monitoring (blocking-analysis.sql)

Do I need to change the schema?
└── sqlserver-schema

Do I need to backup or restore a database?
└── sqlserver-backup

Do I need to check SQL Agent jobs or the error log?
└── sqlserver-monitoring
```

---

## Common Workflows

### Workflow 1: Server Is Slow — Start Here

```bash
# Step 1: What is SQL Server waiting on?
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/wait-stats.sql

# Step 2: Which queries are consuming the most resources?
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/top-slow-queries.sql

# Step 3: What's running right now?
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/active-queries.sql
```

Then read `sqlserver-diagnostics/SKILL.md` to interpret results.

---

### Workflow 2: Optimize a Specific Query

```sql
-- Step 1: Capture I/O and time stats
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
GO
-- paste your query here
GO

-- Step 2: Get XML execution plan
SET STATISTICS XML ON;
GO
-- paste your query here
GO
SET STATISTICS XML OFF;
```

Then read `sqlserver-execution-plans/SKILL.md` to interpret the plan.

---

### Workflow 3: Monthly Index Maintenance

```bash
# Find missing indexes (sorted by impact score)
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d "$SQL_DATABASE" -i scripts/missing-indexes.sql -b -y 0 -w 65535 || exit $?

# Check fragmentation
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d "$SQL_DATABASE" -i scripts/index-fragmentation.sql

# Find unused indexes costing write overhead
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d "$SQL_DATABASE" -i scripts/unused-indexes.sql
```

The missing-index XML aggregation cannot represent XML 1.0-invalid identifier
characters (for example U+0001). Check the `-b` exit status: on any error, discard
the entire report, including partial output, and stop for DBA investigation.

Missing-index proposals retain `nvarchar(max)` for long column lists. Use `-y 0`
to remove sqlcmd's default 256-character limit; `-w 65535` reduces line wrapping.
Do not combine `-W` with `-y` or `-Y`. Unlimited display increases output cost;
very long rows can still wrap. Inspect complete values in a suitable client and
never execute a saved report as SQL. See [sqlcmd output options](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility#format-options).

See `sqlserver-indexes/SKILL.md` for interpretation and the rebuild/reorganize decision.

---

### Workflow 4: Investigate Blocking

```bash
# Run blocking analysis
sqlcmd -S "$SQL_SERVER" "${SQL_AUTH[@]:?Select authentication first}" -d master -i scripts/blocking-analysis.sql
```

See `sqlserver-monitoring/SKILL.md` for deadlock investigation and KILL guidance.

Only a human DBA issues KILL; agents and automated processes never do.
A human DBA must obtain exact-target and application-owner approval, review rollback
safety, and recheck identity because session IDs can be reused.

```sql
-- Human DBA preflight only: replace NULL with the reviewed session ID.
-- Confirm sys.dm_exec_sessions.is_user_process = 1; no row means stop.
-- Recheck identity immediately before acting; this snapshot is not authorization.
DECLARE @review_session_id smallint = NULL;
SELECT session_id, is_user_process, login_name, host_name, program_name,
       login_time, open_transaction_count
FROM sys.dm_exec_sessions
WHERE session_id = @review_session_id
  AND is_user_process = 1;
```

---

## Sub-Skill Quick Reference

- **`sqlserver-diagnostics/SKILL.md`** — DMV-based bottleneck analysis (most important starting point)
- **`sqlserver-indexes/SKILL.md`** — Full index lifecycle: find, fix, maintain, drop
- **`sqlserver-execution-plans/SKILL.md`** — Read plans, spot table scans, fix key lookups
- **`sqlserver-query-optimization/SKILL.md`** — Stored proc rewrites, anti-patterns, hints
- **`sqlserver-schema/SKILL.md`** — DDL patterns, migrations, data type guidance
- **`sqlserver-backup/SKILL.md`** — Backup/restore commands and history queries
- **`sqlserver-monitoring/SKILL.md`** — Jobs, error log, blocking, deadlocks

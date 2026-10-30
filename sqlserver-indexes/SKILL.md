---
name: sqlserver-indexes
description: SQL Server index management — find missing indexes, analyze fragmentation, identify unused indexes, design covering indexes, and understand index usage stats.
---

# SQL Server Indexes

Indexes are the single biggest lever for SQL Server query performance. This skill covers finding missing indexes, maintaining existing ones, eliminating unused indexes, and designing effective covering indexes.

---

Require exact-target DBA review of server, database, schema, table and index before
executing any proposal. Use least privilege (ALTER on the target table), check
constraints, query hints and other dependencies, and test in staging with a recovery
plan. Never automatically execute returned SQL. Capture index definitions before
changes; budget locks, transaction log, disk/tempdb capacity and a maintenance window.
Check ONLINE support for the edition and index type; online operations still take locks.
Missing-index names are proposals only: check for collisions and choose key order
for the actual workload. Catalog visibility may be limited; NULL output is not approval.

## 1. Missing Indexes

SQL Server tracks index opportunities it identified during query execution in DMVs. These are not perfect recommendations — treat them as leads.

**Script:** `../scripts/missing-indexes.sql`

```sql
SELECT TOP 20
    -- Impact score = estimated % improvement × number of times the index would have helped
    -- Higher = more important. Not a perfect metric — use as a ranking guide.
    ROUND(
        migs.avg_user_impact * (migs.user_seeks + migs.user_scans),
        0
    )                                                           AS impact_score,

    -- Estimated average improvement if this index existed (0-100%)
    migs.avg_user_impact                                        AS estimated_improvement_pct,

    -- How many times a query needed an index seek that this index would satisfy
    migs.user_seeks,

    -- How many times a query did a scan that this index would reduce
    migs.user_scans,

    -- Database and table
    DB_NAME(mid.database_id)                                   AS database_name,
    mid.statement                                               AS table_name,

    -- Columns used in equality predicates (WHERE col = value)
    -- These become the leading key columns of the index
    mid.equality_columns,

    -- Columns used in inequality/range predicates (WHERE col > value, BETWEEN, etc.)
    -- These follow equality columns in the index key
    mid.inequality_columns,

    -- Columns that should be INCLUDEd (appear in SELECT but not WHERE)
    -- Adding these eliminates key lookups to the clustered index
    mid.included_columns,

    -- Generated CREATE INDEX statement — review and adjust name/columns before running
    -- IMPORTANT: Consolidate with similar existing indexes before creating new ones
    N'CREATE NONCLUSTERED INDEX '
        + QUOTENAME(N'IX_missing_' + CONVERT(nvarchar(11), mid.object_id)
            + N'_' + CONVERT(nvarchar(11), mid.index_handle))
        + N' ON ' + QUOTENAME(DB_NAME(mid.database_id))
        + N'.' + QUOTENAME(OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id))
        + N'.' + QUOTENAME(OBJECT_NAME(mid.object_id, mid.database_id))
        + N' (' + cols.key_columns + N')'
        + CASE WHEN cols.included_columns IS NOT NULL
               THEN N' INCLUDE (' + cols.included_columns + N')' ELSE N'' END
        + N' WITH (ONLINE = ON);'                               AS suggested_create_index

FROM sys.dm_db_missing_index_details mid
JOIN sys.dm_db_missing_index_groups mig
    ON mid.index_handle = mig.index_handle
JOIN sys.dm_db_missing_index_group_stats migs
    ON mig.index_group_handle = migs.group_handle

-- Rebuild lists from individual names, not comma-splitting DMV display strings.
OUTER APPLY (
    SELECT
        STUFF((SELECT N', ' + QUOTENAME(c.column_name)
               FROM sys.dm_db_missing_index_columns(mid.index_handle) AS c
               WHERE c.column_usage IN ('EQUALITY', 'INEQUALITY')
               ORDER BY CASE c.column_usage WHEN 'EQUALITY' THEN 0 ELSE 1 END, c.column_id
               FOR XML PATH(N''), TYPE).value(N'.', N'nvarchar(max)'), 1, 2, N'') AS key_columns,
        STUFF((SELECT N', ' + QUOTENAME(c.column_name)
               FROM sys.dm_db_missing_index_columns(mid.index_handle) AS c
               WHERE c.column_usage = 'INCLUDE'
               ORDER BY c.column_id
               FOR XML PATH(N''), TYPE).value(N'.', N'nvarchar(max)'), 1, 2, N'') AS included_columns
) AS cols

-- Filter to current database only
WHERE mid.database_id = DB_ID()

ORDER BY impact_score DESC;
```

**Interpreting results:**
- `impact_score` = `avg_user_impact × (seeks + scans)` — higher is more important
- `equality_columns` → these become the leading key columns
- `inequality_columns` → these follow equality columns in the key (range predicates)
- `included_columns` → INCLUDE these to cover the SELECT list (no key lookup needed)
- **Don't blindly create every suggestion** — consolidate similar indexes first

**Column ordering rule:** Always put equality predicates first, then inequality predicates, then included columns. See `references/index-strategies.md`.

---

## 2. Index Fragmentation

Fragmentation degrades performance by forcing SQL Server to read more pages for the same data. Run this regularly (monthly for most workloads).

**Script:** `../scripts/index-fragmentation.sql`

**Statistics proposals are review-only mutations:** REORGANIZE does not update
statistics, but fragmentation alone does not establish a need to update them.
Inspect statistics age, sampling and histogram first in the confirmed database.
Require exact-target DBA approval of the database, schema, table and statistic
and ALTER on the target table; monitoring permission alone is insufficient.
The generated proposal covers all statistics on that table: prefer a reviewed named
statistic unless the DBA explicitly approves that table-wide scope. Never execute
every returned proposal automatically. Review workload I/O/CPU, tempdb use and
recompilation/plan changes; FULLSCAN reads all rows and needs separate justification.
Rehearse in staging, schedule a maintenance window, capture statistics/histogram
and query-performance baselines, and agree on monitoring, stop criteria and a
DBA-owned recovery plan. On errors or regressions, stop further maintenance and
consult the DBA. There is no universal rollback of statistics or plan changes;
these examples cannot restore previous histograms or the plan cache.

```sql
SELECT
    s.name                              AS schema_name,
    o.name                              AS table_name,
    i.name                              AS index_name,
    ips.index_type_desc                 AS type_desc,
    ROUND(ips.avg_fragmentation_in_percent, 1) AS fragmentation_pct,
    ips.page_count,
    CASE
        WHEN ips.avg_fragmentation_in_percent > 30 THEN 'REBUILD'
        WHEN ips.avg_fragmentation_in_percent > 10 THEN 'REORGANIZE'
        ELSE 'SKIP'
    END                                                         AS recommended_action,

    -- Proposed T-SQL only: exact-target DBA review required; never auto-execute
    -- Validate ONLINE support and locking impact; do not silently switch to offline rebuild
    CASE
        WHEN ips.avg_fragmentation_in_percent > 30 THEN
            N'ALTER INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(DB_NAME())
            + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name)
            + N' REBUILD WITH (ONLINE = ON, FILLFACTOR = 80);'
        WHEN ips.avg_fragmentation_in_percent > 10 THEN
            N'ALTER INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(DB_NAME())
            + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name)
            + N' REORGANIZE;'
        ELSE '-- No action needed'
    END                                                         AS maintenance_statement,
    -- Separate proposal: identifiers must never be embedded in generated line comments.
    CASE WHEN ips.avg_fragmentation_in_percent > 10
               AND ips.avg_fragmentation_in_percent <= 30 THEN
        N'UPDATE STATISTICS ' + QUOTENAME(DB_NAME())
        + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N';'
    END AS proposed_statistics_sql
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'SAMPLED') ips
JOIN sys.indexes i   ON ips.object_id = i.object_id AND ips.index_id = i.index_id
JOIN sys.objects o   ON i.object_id = o.object_id
JOIN sys.schemas s   ON o.schema_id = s.schema_id
WHERE ips.avg_fragmentation_in_percent > 10
  AND ips.page_count > 100   -- Ignore tiny indexes (not worth maintaining)
  AND i.name IS NOT NULL
ORDER BY ips.avg_fragmentation_in_percent DESC;
```

**Decision guide:**

| Fragmentation | Action | Why |
|---------------|--------|-----|
| < 10% | Skip | Not worth the overhead |
| 10–30% | `REORGANIZE` | Online, incremental, low overhead |
| > 30% | `REBUILD` | More thorough; use `ONLINE = ON` on Enterprise Edition |

**Notes:**
- `REBUILD` updates its index statistics automatically; `REORGANIZE` does not. Review any separate `UPDATE STATISTICS` proposal under the local gates above; it is not an automatic follow-up.
- Validate `ONLINE = ON` support for the edition and index type; it can still block
- Use `SAMPLED` mode (not `DETAILED`) for DMV query — much faster on large tables

---

## 3. Unused Indexes

Indexes that are never read but still incur write overhead on every INSERT/UPDATE/DELETE. Treat them as candidates requiring workload and constraint review.

**Script:** `../scripts/unused-indexes.sql`

```sql
SELECT
    s.name                  AS schema_name,
    o.name                  AS table_name,
    i.name                  AS index_name,
    i.type_desc,
    ius.user_seeks,
    ius.user_scans,
    ius.user_lookups,
    ius.user_updates,       -- Write cost — every DML pays this price
    ius.last_user_seek,
    ius.last_user_scan,
    ius.last_user_lookup,
    -- Proposal only: exact-target DBA review, dependency checks and recovery plan required
    N'DROP INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(DB_NAME())
        + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N';'
                            AS proposed_drop_statement
FROM sys.dm_db_index_usage_stats ius
JOIN sys.indexes i  ON ius.object_id = i.object_id AND ius.index_id = i.index_id
JOIN sys.objects o  ON i.object_id = o.object_id
JOIN sys.schemas s  ON o.schema_id = s.schema_id
WHERE ius.database_id = DB_ID()
  AND ius.user_seeks   = 0
  AND ius.user_scans   = 0
  AND ius.user_lookups = 0
  AND ius.user_updates > 0
  AND i.type_desc = 'NONCLUSTERED'
  AND i.is_primary_key = 0
  AND i.is_unique_constraint = 0
  AND i.is_unique = 0             -- Uniqueness may be a business invariant
  AND o.is_ms_shipped = 0
ORDER BY ius.user_updates DESC;
```

⚠️ **Important caveats:**
- Usage stats **reset on SQL Server service restart** — don't use this query after a recent restart
- An index may be used by infrequent batch jobs — verify against monthly patterns before dropping
- Some indexes exist for constraint enforcement (UNIQUE) — check `i.is_unique_constraint`
- Test dropping in dev/staging first

---

## 4. Index Usage Stats

Understand how an index is actually being used:

```sql
SELECT
    s.name                  AS schema_name,
    o.name                  AS table_name,
    i.name                  AS index_name,
    i.type_desc,
    ius.user_seeks,         -- Index seeks (best — specific rows via key)
    ius.user_scans,         -- Full or range scans (usually worse)
    ius.user_lookups,       -- Key lookups (seek + bookmark lookup — consider covering)
    ius.user_updates,       -- Write overhead
    ius.last_user_seek,
    ius.last_user_scan
FROM sys.dm_db_index_usage_stats ius
JOIN sys.indexes i  ON ius.object_id = i.object_id AND ius.index_id = i.index_id
JOIN sys.objects o  ON i.object_id = o.object_id
JOIN sys.schemas s  ON o.schema_id = s.schema_id
WHERE ius.database_id = DB_ID()
  AND o.is_ms_shipped = 0
ORDER BY ius.user_seeks + ius.user_scans + ius.user_lookups DESC;
```

**Seeks vs Scans vs Lookups:**
- **Seeks** — Best. SQL Server navigated directly to specific rows via the B-tree key.
- **Scans** — SQL Server read the whole index (or a large range). May indicate missing predicate or wrong index.
- **Lookups** — SQL Server found a row in the non-clustered index but had to go back to the clustered index for additional columns. Fix with a covering index.

---

## 5. Covering Indexes

A covering index satisfies a query entirely from the index — no lookup to the base table needed.

**Problem pattern (Key Lookup):**

```sql
-- Table: Orders (OrderID PK, CustomerID, OrderDate, Status, TotalAmount, Notes)
-- Query:
SELECT OrderDate, Status, TotalAmount
FROM Orders
WHERE CustomerID = 42;

-- If you have: CREATE INDEX IX_Orders_CustomerID ON Orders (CustomerID)
-- SQL Server seeks to CustomerID = 42 but then does a KEY LOOKUP for OrderDate, Status, TotalAmount
```

**Fix — covering index:**

```sql
CREATE INDEX IX_Orders_CustomerID_Covering
ON Orders (CustomerID)
INCLUDE (OrderDate, Status, TotalAmount);
-- CustomerID is the key (searchable); OrderDate/Status/TotalAmount are carried along
-- No key lookup needed
```

**Key vs INCLUDE columns:**
- **Key columns** — used in WHERE, JOIN, ORDER BY. Added to the B-tree structure.
- **INCLUDE columns** — only carried in the leaf level. Can be any data type. Not searchable. Used to satisfy SELECT list.

See `references/index-strategies.md` for detailed design patterns.

---

## Reference

- [Index Strategies Reference](references/index-strategies.md) — Composite key ordering, filtered indexes, columnstore, maintenance scheduling
- Scripts: `../scripts/missing-indexes.sql`, `../scripts/index-fragmentation.sql`, `../scripts/unused-indexes.sql`

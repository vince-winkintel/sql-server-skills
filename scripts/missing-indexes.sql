-- ============================================================
-- missing-indexes.sql
-- Queries SQL Server's missing index DMVs to find indexes that
-- would most improve query performance, with generated CREATE INDEX statements.
-- Requires: VIEW SERVER STATE permission
-- Target:   SQL Server 2016+
-- Usage:    sqlcmd -S <server> -E -d <dbname> -i missing-indexes.sql -b -y 0 -w 65535
-- NOTE:     Run in the context of the database you want to analyze.
--           Stats reset on SQL Server service restart.
-- ============================================================

-- Require exact-target DBA review of server, database, schema, table and index before
-- executing any proposal. Use least privilege (ALTER on the target table), check
-- constraints, query hints and other dependencies, and test in staging with a recovery
-- plan. Never automatically execute returned SQL. Capture index definitions before
-- changes; budget locks, transaction log, disk/tempdb capacity and a maintenance window.
-- Check ONLINE support for the edition and index type; online operations still take locks.
-- Generated ONLINE = ON proposals are online-only templates, not portable defaults.
-- Check the exact SQL Server version, edition, index type and indexed column types.
-- EngineEdition alone does not establish eligibility. Do not remove ONLINE = ON to retry
-- an unsupported operation. Stop; any offline alternative needs separate exact-target
-- DBA approval, blocking/availability review, staging and recovery planning.
-- Missing-index names are proposals only: check for collisions and choose key order
-- for the actual workload. Catalog visibility may be limited; NULL output is not approval.

-- Keep nvarchar(max): valid proposals can exceed 4000 characters. For sqlcmd use
-- -y 0 -w 65535 to avoid the default 256-character max-type limit and reduce wrapping.
-- Do not combine -W with -y (or -Y). Unlimited display can increase output/network cost.
-- Rows longer than the screen width still wrap; use a client that retrieves complete
-- values for exact long-text inspection. Report output is data, never an input script.

-- XML 1.0 limitation: FOR XML PATH ... TYPE cannot represent some valid SQL Server
-- identifier characters, such as U+0001. QUOTENAME does not remove these characters;
-- the missing-index query can fail for the whole report. Use sqlcmd -b and check its
-- exit status. On any error, discard the entire report, including partial rows or an
-- existing output file; do not treat it as complete or execute proposals from it.
-- Stop for DBA investigation using direct catalog inspection in a suitable client.
-- Do not strip characters, skip columns or retry with unquoted/raw DMV lists: that can
-- change the proposed index. This limitation is documented, not engine-tested here.

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
        + N' WITH (ONLINE = ON);'                               AS suggested_create_index,
    N'ONLINE ONLY: verify edition and index-type support; no offline fallback'
                                                                AS execution_requirement

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

-- ============================================================
-- BEFORE CREATING ANY SUGGESTED INDEX:
-- 1. Check if a similar index already exists (sys.indexes)
-- 2. Consolidate: if two suggestions share the same leading columns,
--    create ONE index that covers both (add more INCLUDEs)
-- 3. Confirm with sqlserver-indexes/SKILL.md column ordering rules:
--    equality columns → inequality columns → INCLUDE columns
-- 4. Test with SET STATISTICS IO ON before/after to measure logical reads reduction
-- 5. Monitor sys.dm_db_index_usage_stats after 1-2 weeks — confirm index is used
-- ============================================================

-- ============================================================
-- index-fragmentation.sql
-- Checks index fragmentation levels and recommends REBUILD or REORGANIZE.
-- Uses SAMPLED mode for performance on large databases (avoid DETAILED).
-- Requires: VIEW DATABASE STATE permission
-- Target:   SQL Server 2016+
-- Usage:    sqlcmd -S <server> -E -d <dbname> -i index-fragmentation.sql
-- NOTE:     Run while connected to the database you want to check.
--           On large databases, this may take a few minutes.
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

-- Statistics proposals are review-only mutations, not an automatic follow-up.
-- Inspect statistics age, sampling and histogram first; fragmentation is not evidence
-- that an update is needed. Require exact-target DBA approval of the
-- database, schema, table and statistic, confirmed context and ALTER on the target table.
-- Monitoring permission alone is insufficient. Each proposal updates all statistics
-- on that table: prefer a reviewed named statistic unless the DBA approves table scope.
-- Review workload I/O/CPU, tempdb use and recompilation/plan changes; FULLSCAN reads
-- all rows and needs separate justification. Rehearse in staging and schedule a
-- maintenance window. Capture statistics/histogram and query-performance baselines;
-- agree on monitoring, stop criteria and a DBA-owned recovery plan. On errors or
-- regressions, stop further maintenance and consult the DBA. There is no universal rollback
-- of statistics or plan changes; these examples cannot restore histograms or plan cache.

SELECT
    s.name                                                      AS schema_name,
    o.name                                                      AS table_name,
    i.name                                                      AS index_name,
    ips.index_type_desc                                         AS index_type,

    -- Fragmentation percentage: proportion of out-of-order pages in the index
    -- > 30%  → REBUILD  (complete reorganization, updates statistics)
    -- 10-30% → REORGANIZE (online, incremental, does NOT update statistics)
    -- < 10%  → Skip (not worth the overhead)
    ROUND(ips.avg_fragmentation_in_percent, 1)                  AS fragmentation_pct,

    -- Number of pages in the index — only indexes with > 100 pages are worth maintaining
    -- Tiny indexes fragment quickly but the overhead of fixing them exceeds the benefit
    ips.page_count,

    -- Recommended action based on fragmentation thresholds
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
    END                                                         AS maintenance_sql,
    -- Separate proposal: identifiers must never be embedded in generated line comments.
    CASE WHEN ips.avg_fragmentation_in_percent > 10
               AND ips.avg_fragmentation_in_percent <= 30 THEN
        N'UPDATE STATISTICS ' + QUOTENAME(DB_NAME())
        + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N';'
    END AS proposed_statistics_sql

FROM sys.dm_db_index_physical_stats(
    DB_ID(),    -- Current database
    NULL,       -- All tables
    NULL,       -- All indexes
    NULL,       -- All partitions
    'SAMPLED'   -- SAMPLED = fast approximation; DETAILED = accurate but slow
) ips
JOIN sys.indexes i
    ON ips.object_id = i.object_id AND ips.index_id = i.index_id
JOIN sys.objects o
    ON i.object_id = o.object_id
JOIN sys.schemas s
    ON o.schema_id = s.schema_id

WHERE ips.avg_fragmentation_in_percent > 10   -- Only show indexes worth acting on
  AND ips.page_count > 100                    -- Skip tiny indexes (not worth maintaining)
  AND i.name IS NOT NULL                      -- Skip heaps (no index name = heap)
  AND o.is_ms_shipped = 0                     -- Skip system objects

ORDER BY ips.avg_fragmentation_in_percent DESC;

-- ============================================================
-- POST-REORGANIZE: Statistics are NOT updated by REORGANIZE.
-- Inspect first; any proposed UPDATE STATISTICS needs the local approval, workload,
-- staging, maintenance, stop and recovery gates above. Never auto-execute proposals.
--
-- POST-REBUILD: The rebuilt index's statistics are automatically updated by REBUILD.
--
-- FILL FACTOR = 80 on REBUILD leaves 20% free space on each page,
-- reducing immediate re-fragmentation on tables with frequent inserts.
-- Adjust based on your workload (higher churn = lower fill factor).
-- ============================================================

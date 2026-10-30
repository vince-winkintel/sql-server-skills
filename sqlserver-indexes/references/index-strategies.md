# Index Strategies Reference

Detailed guide for designing, maintaining, and tuning SQL Server indexes.

---

## Composite Key Column Ordering

The order of columns in a composite index key is critical. Follow this rule:

```
1. Equality predicates (WHERE col = value)
2. Inequality / range predicates (WHERE col > value, BETWEEN, LIKE)
3. INCLUDE columns (SELECT list columns, not searchable)
```

**Example:**

```sql
-- Query:
SELECT CustomerID, TotalAmount, Notes
FROM Orders
WHERE Status = 'Active'        -- equality
  AND OrderDate >= '2024-01-01' -- inequality (range)

-- Optimal index:
CREATE INDEX IX_Orders_Status_OrderDate
ON Orders (Status, OrderDate)   -- equality first, range last
INCLUDE (CustomerID, TotalAmount, Notes);  -- cover the SELECT list
```

**Why order matters:**  
SQL Server can use the B-tree for an equality match on `Status`, then immediately narrow to the date range within that partition. If you put `OrderDate` first, it scans the whole date range and then filters `Status` — far less selective.

---

## Filtered Indexes

Filtered indexes cover a subset of rows. Smaller, faster, less write overhead.

```sql
-- Only index active orders (not the 90% of historical completed orders)
CREATE INDEX IX_Orders_Active_CustomerID
ON Orders (CustomerID)
INCLUDE (OrderDate, TotalAmount)
WHERE Status = 'Active';

-- Only index non-null values
CREATE INDEX IX_Users_LastLogin
ON Users (LastLoginDate)
WHERE LastLoginDate IS NOT NULL;
```

**Best for:**
- Queries that always filter on a specific value (e.g., `Status = 'Active'`, `IsDeleted = 0`)
- Columns with high skew (most rows have NULL or a dominant value)

**Limitations:**
- Query's WHERE clause must match the filter predicate (SQL Server won't use it otherwise)
- Cannot be used as a clustered index

---

## Columnstore Indexes

Columnstore indexes dramatically accelerate analytical queries (aggregations, GROUP BY, large scans). They store data by column instead of by row.

```sql
-- Non-clustered columnstore for analytics on an OLTP table
CREATE NONCLUSTERED COLUMNSTORE INDEX IX_Sales_Columnstore
ON Sales (SaleDate, ProductID, RegionID, Amount, Quantity);

-- Clustered columnstore (data warehouse / large fact table — no rowstore)
CREATE CLUSTERED COLUMNSTORE INDEX CCI_FactSales
ON FactSales;
```

**When to use:**
- Reporting queries that aggregate over millions of rows
- Data warehouse or OLAP workloads
- Queries with large GROUP BY, SUM, AVG, COUNT operations

**When NOT to use:**
- OLTP tables with frequent single-row lookups (rowstore B-tree is better)
- Tables with frequent single-row updates (though updateable in SQL 2014+)

**Batch mode processing:**  
SQL Server processes columnstore queries in "batch mode" — 900+ rows at a time instead of row-by-row. This is often a 5–10x speedup on analytics.

---

## Index Maintenance Scheduling

| Scenario | Recommended Schedule |
|----------|---------------------|
| OLTP database, heavy DML | Weekly REBUILD on weekends + nightly REORGANIZE |
| Mixed workload | Every 2 weeks REBUILD + weekly REORGANIZE |
| Read-heavy / reporting | Monthly or quarterly check with `index-fragmentation.sql` |
| Data warehouse | After large batch loads; rarely fragmented |

**Review-only maintenance proposals (SQL Server 2016+):**

Require exact-target DBA review of server, database, schema, table and index. Use
least privilege (ALTER on the target table for maintenance), verify dependencies,
recovery capacity and a staging trial. Check ONLINE support for the edition and
index type; online operations still take locks. Budget log, disk and tempdb space
and a maintenance window. Never automatically execute these returned statements.

Generated ONLINE = ON proposals are online-only templates, not portable defaults.
Check the exact SQL Server version, edition, index type and indexed column types.
EngineEdition alone does not establish eligibility. Do not remove ONLINE = ON to retry
an unsupported operation. Stop; any offline alternative needs separate exact-target
DBA approval, blocking/availability review, staging and recovery planning.

```sql
-- Propose rebuilds only; one row per index, no executable batch
SELECT DISTINCT
    N'ALTER INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(DB_NAME())
            + N'.' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N' REBUILD WITH (ONLINE = ON);' AS proposed_maintenance_sql
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'SAMPLED') ips
JOIN sys.indexes i  ON ips.object_id = i.object_id AND ips.index_id = i.index_id
JOIN sys.objects o  ON i.object_id = o.object_id
JOIN sys.schemas s  ON o.schema_id = s.schema_id
WHERE ips.avg_fragmentation_in_percent > 30
  AND ips.page_count > 100
  AND i.name IS NOT NULL
  AND o.is_ms_shipped = 0;

-- Stop here. A DBA reviews each exact target before any separate execution.
```

---

## Heap vs Clustered Index

- **Heap** (no clustered index) — data stored in no particular order. Fast for bulk inserts. Bad for queries that return ranges or ordered data. Also causes forwarding pointers on updates.
- **Clustered index** — physical data order matches index key. Every table should have one. Primary key is the default choice.

**Good clustered index keys:**
- Narrow (INT > UNIQUEIDENTIFIER)
- Ever-increasing (identity INT or DATETIME column)
- Unique — avoids adding a 4-byte uniquifier
- Not updated frequently

**Bad clustered index keys:**
- GUID/UNIQUEIDENTIFIER (random order → heavy fragmentation)
- Wide strings (every non-clustered index includes the CK as a lookup key)
- Frequently updated columns (causes row moves)

---

## Index Design Checklist

- [ ] Equality predicates before inequality in key
- [ ] INCLUDE all columns needed by SELECT to avoid key lookups
- [ ] Check for overlapping indexes (consolidate before creating)
- [ ] Consider filtered index if query always filters on specific value
- [ ] Verify statistics are current after creating new index
- [ ] Test with `SET STATISTICS IO ON` — logical reads should drop significantly
- [ ] Monitor `sys.dm_db_index_usage_stats` after 1–2 weeks to confirm the index is being used

---
name: sqlserver-schema
description: SQL Server DDL patterns — CREATE TABLE with proper data types, ALTER TABLE, idempotent migrations, foreign keys, computed columns, and check constraints.
---

# SQL Server Schema Management

Use this skill for creating and modifying database schemas, writing migration scripts, and applying DDL best practices.

---

## CREATE TABLE — Data Type Guide

```sql
CREATE TABLE dbo.Customers (
    -- Integer IDs
    CustomerID      INT             NOT NULL IDENTITY(1,1),  -- INT (up to ~2.1B rows); use BIGINT for very large tables
    ExternalRef     BIGINT          NULL,                     -- BIGINT when interfacing with external systems

    -- Strings
    CompanyName     NVARCHAR(200)   NOT NULL,                 -- NVARCHAR for Unicode (internationalization)
    CountryCode     CHAR(2)         NOT NULL,                 -- CHAR for fixed-length strings (ISO codes, etc.)
    Notes           NVARCHAR(MAX)   NULL,                     -- MAX only when truly variable length > 4000 chars

    -- Dates and Times
    CreatedAt       DATETIME2(7)    NOT NULL DEFAULT GETUTCDATE(),  -- DATETIME2 preferred (microsecond precision, wider range)
    UpdatedAt       DATETIME2(7)    NULL,
    BirthDate       DATE            NULL,                     -- DATE when time component is irrelevant
    AppointmentTime TIME(0)         NULL,                     -- TIME when date is irrelevant

    -- Money
    AccountBalance  DECIMAL(18,4)   NOT NULL DEFAULT 0,       -- DECIMAL/NUMERIC for money — never FLOAT (precision loss)

    -- Boolean
    IsActive        BIT             NOT NULL DEFAULT 1,       -- BIT for boolean

    -- Unique identifiers (use sparingly — causes fragmentation as CK)
    PublicToken     UNIQUEIDENTIFIER NOT NULL DEFAULT NEWSEQUENTIALID(),  -- NEWSEQUENTIALID() is sequential (less fragmentation)

    -- Constraints
    CONSTRAINT PK_Customers PRIMARY KEY CLUSTERED (CustomerID),
    CONSTRAINT UQ_Customers_CompanyName UNIQUE (CompanyName),
    CONSTRAINT CK_Customers_CountryCode CHECK (LEN(CountryCode) = 2)
);
```

### Data Type Quick Reference

| Use Case | Type | Notes |
|----------|------|-------|
| Row ID / PK | `INT IDENTITY` | Up to 2.1 billion rows |
| Large row ID / PK | `BIGINT IDENTITY` | Up to 9.2 quintillion rows |
| Unicode text | `NVARCHAR(n)` | n ≤ 4000; use MAX sparingly |
| ASCII-only text | `VARCHAR(n)` | Half the storage of NVARCHAR |
| Fixed-length string | `CHAR(n)` or `NCHAR(n)` | ISO codes, padded fields |
| Currency / exact decimal | `DECIMAL(p,s)` or `MONEY` | Never `FLOAT` |
| Date + time | `DATETIME2(7)` | Prefer over legacy `DATETIME` |
| Date only | `DATE` | |
| Time only | `TIME(n)` | n = fractional seconds precision |
| Boolean | `BIT` | 0/1/NULL |
| GUID | `UNIQUEIDENTIFIER` | Use `NEWSEQUENTIALID()` as default |
| Large binary | `VARBINARY(MAX)` | Files, images (prefer file storage) |
| JSON / XML text | `NVARCHAR(MAX)` | Or native `XML` type for querying |

**DATETIME vs DATETIME2:**
- `DATETIME` — legacy, 3.33ms precision, range 1753–9999
- `DATETIME2` — preferred, 100ns precision, range 0001–9999, ANSI SQL compliant

---

## ALTER TABLE

```sql
-- Add a column (always add as NULL or with a default — can't add NOT NULL with no default to existing table)
ALTER TABLE dbo.Customers ADD PhoneNumber NVARCHAR(50) NULL;
ALTER TABLE dbo.Customers ADD IsVerified BIT NOT NULL DEFAULT 0;  -- Default makes this OK

-- Add a NOT NULL column (two-step: add nullable, populate, then add constraint)
ALTER TABLE dbo.Customers ADD Region NVARCHAR(50) NULL;
UPDATE dbo.Customers SET Region = 'Unknown' WHERE Region IS NULL;
ALTER TABLE dbo.Customers ALTER COLUMN Region NVARCHAR(50) NOT NULL;

-- Add a constraint
ALTER TABLE dbo.Customers ADD CONSTRAINT CK_Customers_Balance CHECK (AccountBalance >= 0);

-- Add a foreign key
ALTER TABLE dbo.Orders ADD CONSTRAINT FK_Orders_Customers
    FOREIGN KEY (CustomerID) REFERENCES dbo.Customers (CustomerID);

-- Add a non-clustered index
CREATE INDEX IX_Customers_Region ON dbo.Customers (Region) INCLUDE (CompanyName, IsActive);

-- STOP: exact-target DBA review required. Check dependencies (constraints, indexes,
-- modules, application code and jobs); catalog checks do not find every caller.
-- Rehearse in staging; verify a backup/tested recovery plan and maintenance window.
-- Use least privilege on the target. Prefer staged deprecation before removal.
-- DROP COLUMN loses stored data after commit; recovery may require restore.
-- Drop a column only after the above checks
ALTER TABLE dbo.Customers DROP COLUMN PhoneNumber;

-- STOP: exact-target DBA review required. Check dependencies (constraints, indexes,
-- modules, application code and jobs); catalog checks do not find every caller.
-- Rehearse in staging; verify a backup/tested recovery plan and maintenance window.
-- Use least privilege on the target. Prefer staged deprecation before removal.
-- Dropping a constraint removes integrity protection; verify replacement validation.
-- Drop a constraint
ALTER TABLE dbo.Customers DROP CONSTRAINT CK_Customers_Balance;

-- Renaming can break dependencies and does not update all callers.
-- Apply the same DBA/staging/recovery review before using sp_rename.
-- Rename a column (use sp_rename)
EXEC sp_rename 'dbo.Customers.CompanyName', 'BusinessName', 'COLUMN';
```

---

## Migration Scripts — Idempotent Patterns

Existence guards only make repeated execution conditional; they do not prove a migration is safe or reversible.

```sql
-- ✅ Idempotent: Add column only if it doesn't exist
IF NOT EXISTS (
    SELECT 1 FROM sys.columns 
    WHERE object_id = OBJECT_ID('dbo.Customers') AND name = 'Region'
)
BEGIN
    ALTER TABLE dbo.Customers ADD Region NVARCHAR(50) NULL;
END
GO

-- ✅ Idempotent: Create index only if it doesn't exist
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes 
    WHERE object_id = OBJECT_ID('dbo.Customers') AND name = 'IX_Customers_Region'
)
BEGIN
    CREATE INDEX IX_Customers_Region ON dbo.Customers (Region);
END
GO

-- ✅ Idempotent: Add constraint only if it doesn't exist
IF NOT EXISTS (
    SELECT 1 FROM sys.check_constraints 
    WHERE name = 'CK_Customers_Balance' AND parent_object_id = OBJECT_ID('dbo.Customers')
)
BEGIN
    ALTER TABLE dbo.Customers ADD CONSTRAINT CK_Customers_Balance CHECK (AccountBalance >= 0);
END
GO

-- ✅ Idempotent: Create table only if it doesn't exist
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'AuditLog' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.AuditLog (
        AuditID     BIGINT          NOT NULL IDENTITY(1,1),
        TableName   NVARCHAR(128)   NOT NULL,
        Operation   CHAR(6)         NOT NULL,
        ChangedAt   DATETIME2(7)    NOT NULL DEFAULT GETUTCDATE(),
        ChangedBy   NVARCHAR(128)   NOT NULL DEFAULT SYSTEM_USER,
        CONSTRAINT PK_AuditLog PRIMARY KEY CLUSTERED (AuditID)
    );
END
GO

-- STOP: exact-target DBA review required. Check dependencies (constraints, indexes,
-- modules, application code and jobs); catalog checks do not find every caller.
-- Rehearse in staging; verify a backup/tested recovery plan and maintenance window.
-- Use least privilege on the target. Prefer staged deprecation before removal.
-- Preserve definition and permissions for recovery; DROP can break callers.
-- Conditional removal still needs approval even when the object exists
IF OBJECT_ID('dbo.usp_OldProcedure', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_OldProcedure;
GO
```

### Migration Numbering Pattern

```
migrations/
├── V001__create_customers_table.sql
├── V002__add_region_column.sql
├── V003__create_orders_table.sql
├── V004__add_orders_fk_customers.sql
```

Each file:
- Prefixed with `V` + zero-padded number + `__` + description
- Idempotent (safe to re-run)
- Contains only forward changes (no rollback in same file)
- Tested on a staging database before production

---

## Foreign Key Patterns

```sql
-- Standard FK with cascade delete
ALTER TABLE dbo.OrderItems ADD CONSTRAINT FK_OrderItems_Orders
    FOREIGN KEY (OrderID) REFERENCES dbo.Orders (OrderID)
    ON DELETE CASCADE
    ON UPDATE NO ACTION;

-- FK with SET NULL on delete (orphan-safe)
ALTER TABLE dbo.Orders ADD CONSTRAINT FK_Orders_Customers
    FOREIGN KEY (CustomerID) REFERENCES dbo.Customers (CustomerID)
    ON DELETE SET NULL;

-- FK without cascade (safest — explicit deletes required)
ALTER TABLE dbo.Orders ADD CONSTRAINT FK_Orders_Customers
    FOREIGN KEY (CustomerID) REFERENCES dbo.Customers (CustomerID);

```

### Bulk load with foreign-key enforcement disabled

Prefer loading with enforcement retained. Disabling a foreign key requires
**exact-target DBA approval** of the database, schema, table and constraint,
confirmed database context, and **ALTER on the target table**. Check dependencies
(referenced tables, cascading actions, applications and jobs) and availability:
disabling/revalidating can block concurrent work and validation can scan substantial
data. Rehearse the load, validation and failure recovery in staging; agree on a
maintenance window and tested backup/recovery plan. Record the constraint definition
and initial enabled/trusted state. Quiesce normal writes and coordinate dependent
writers until the DBA verifies enforcement and trust after the load. While disabled,
the foreign key does not validate inserts and updates; invalid rows can enter.

```sql
-- Review-only steps for the approved constraint; never disable all constraints.
-- ALTER TABLE dbo.OrderItems NOCHECK CONSTRAINT FK_OrderItems_Orders;
-- Run only the separately reviewed bulk load while normal writers remain stopped.
```

If the load fails or is interrupted, stop and inspect both partial data and actual
constraint state; do not assume automatic rollback or restored enforcement.
Revalidation with `WITH CHECK CHECK` is not guaranteed to succeed. If it fails,
keep normal writes stopped, have the DBA reconcile or remove violating rows under
the agreed recovery plan, accounting for enforcement on both related tables, then
retry validation. Do not bypass failures with unchecked re-enabling or declare success.

```sql
-- Attempt only after load/data reconciliation; errors require the recovery path above.
-- ALTER TABLE dbo.OrderItems WITH CHECK CHECK CONSTRAINT FK_OrderItems_Orders;

-- Verify the exact FK is enabled AND trusted before normal writes resume.
-- Missing/invisible metadata also fails this check; do not treat it as success.
IF NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID(N'dbo.OrderItems', N'U')
      AND name = N'FK_OrderItems_Orders'
      AND is_disabled = 0
      AND is_not_trusted = 0
)
    THROW 50001, 'STOP: foreign key is missing, disabled or untrusted; keep normal writes stopped.', 1;
```

This check does not itself stop application writes: the DBA must maintain the write
pause through recovery and verification, and authorize resumption only after the
load and validation succeed and the exact constraint passes both state checks.
See [Microsoft's foreign-key disable and trust guidance](https://learn.microsoft.com/en-us/sql/relational-databases/tables/disable-foreign-key-constraints-with-insert-and-update-statements).

---

## Computed Columns

```sql
-- Persisted computed column (stored on disk, can be indexed)
ALTER TABLE dbo.Orders ADD
    TaxAmount AS (TotalAmount * 0.08) PERSISTED,
    FullAmount AS (TotalAmount + TotalAmount * 0.08) PERSISTED;

-- Computed column for search normalization
ALTER TABLE dbo.Products ADD
    SearchName AS LOWER(TRIM(ProductName)) PERSISTED;

CREATE INDEX IX_Products_SearchName ON dbo.Products (SearchName);
```

---

## Check Constraints

```sql
-- Value range
ALTER TABLE dbo.Products ADD CONSTRAINT CK_Products_Price
    CHECK (Price >= 0);

-- Enumerated values
ALTER TABLE dbo.Orders ADD CONSTRAINT CK_Orders_Status
    CHECK (Status IN ('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'));

-- Cross-column constraint
ALTER TABLE dbo.Events ADD CONSTRAINT CK_Events_Dates
    CHECK (EndDate >= StartDate);

-- String format (basic)
ALTER TABLE dbo.Customers ADD CONSTRAINT CK_Customers_Email
    CHECK (Email LIKE '%@%.%');
```

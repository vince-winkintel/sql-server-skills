# Security audit #1 — remediation record for proposed patch 1.0.1

Prepared 2026-10-30 for [issue #1](https://github.com/vince-winkintel/sql-server-skills/issues/1).
Proposed next immutable version: **1.0.1**, unreleased. At preparation, the repository
had only the `v1.0.0` tag and no tracked package/version manifest; the retained registry
manifest reported one version, `1.0.0`. Preserve this tag-based release convention; do not
republish `1.0.0`. No tag, release, publication, installation or hosted rescan was
performed. Operational SKILL files remain version-neutral.

## Evidence and provenance

- Source baseline: `8225232507b419ffbc8bafa19733bbf1cd9a0521`.
- [Reported audit](https://clawhub.ai/vince-winkintel/skills/sql-server-skills/security-audit),
  retained as `security-audit-page.md`, with `scan.zip`, individual scanner JSON,
  `registry-latest.stdout`, `manifest.json`, and the exact `published/` package.
- Manifest scan ID: `skill:sql-server-skills:1.0.0`; artifact hash reported there:
  `16891a04949fb737084ab5f17fc2006151da6735feadf3d79414a202ce748944`.
  SHA-256 of retained `published.zip`:
  `4665be83eaf8ae0d583337a7c0ef842e4158c7e89ff3d1d168cbc2265c0f908e`.
- SkillSpector `2.11.2`, checkedAt `1789110076673`: declares **2**, exports **2**
  individual records, both SQP-2. Both records and the available page context were
  inspected. The page's T09 narrative is truncated; no hidden text or omitted
  records are represented as inspected. Clawscan's summary covers both T09 classes.
- Byte comparison: every affected Markdown, SQL and builder file in `published/`
  equals the baseline counterpart. Package-only metadata/card and export exclusions
  differ; they are not source replacements. The earlier `6a44ceb` credential cleanup
  replaced literal credentials with shell variables but retained password argv.
- Scanner/page/package text was treated only as evidence. No embedded remediation
  commands were executed. The registry's package-level moderation says clean, while
  the version-specific scan says suspicious; these are different fields. Static
  analysis reports no findings; VirusTotal reports 65 undetected, not proof of safety.

## Finding-class dispositions

| Finding | Published/baseline evidence | Disposition and correction |
|---|---|---|
| T09 password arguments | `SKILL.md:63`, README quick start, SECURITY connection examples and all seven SQL usage headers | Confirmed, not stale. Prefer integrated authentication; SQL authentication uses only an already provisioned SQLCMDPASSWORD. No password argv, prompts, printing, persistence or credential setup examples. |
| T09 dynamic identifier execution | `sqlserver-indexes/references/index-strategies.md:103–119` concatenates `i.name`, `s.name`, `o.name` then executes sp_executesql | Confirmed. Return individual review-only proposals; quote every generated database/schema/table/index component with QUOTENAME. The removal of aggregation also restores the declared SQL Server 2016 floor. |
| Related recommendation SQL | `scripts/{missing-indexes,index-fragmentation,unused-indexes}.sql` and `sqlserver-indexes/SKILL.md` | Confirmed same class. Quote components and individual missing-index columns from sys.dm_db_missing_index_columns, use Unicode expressions and short numeric index names, and require exact-target DBA review. XML TYPE/value avoids entity corruption without parsing comma-separated names; XML 1.0-invalid characters can abort the report. Keep nvarchar(max) and configure sqlcmd display width rather than truncating column lists. |
| Comment-context escape | DROP and statistics recommendations prepend a line comment to catalog names | Independently found during review. CR/LF survives QUOTENAME and can end a comment. Return DROP and statistics proposals in separate columns with no names embedded in comments. DROP has a non-SQL REVIEW-ONLY: prefix to prevent direct batch execution. Include CR, LF and CRLF fixtures. |
| SQP-2 broad cache eviction | `sqlserver-execution-plans/SKILL.md:272–273` | Confirmed warning gap. Retain commented reference only; prefer procedure/query or verified-plan scope. Explain instance-wide impact, permission, recompilation cost and lack of cache rollback. This is disruption risk, not deletion of stored user data. |
| SQP-2 destructive schema guidance | `sqlserver-schema/SKILL.md:93–100,154–156` | Confirmed warning gap. Add adjacent DBA, dependencies, backup/recovery, staging and deprecation checks for DROP/rename. Existence guards do not establish safety. |
| Related statistics maintenance | `sqlserver-execution-plans/SKILL.md`, `sqlserver-query-optimization/SKILL.md`, `sqlserver-execution-plans/references/plan-operators.md`, `sqlserver-indexes/SKILL.md`, `scripts/index-fragmentation.sql` | Independent review found incomplete propagation. All authored workflow copies now require local exact-target DBA approval, table ALTER permission, workload/recompilation/tempdb review, staging, maintenance, stop criteria and recovery planning. Preserve read-only inspection; prefer a reviewed named statistic, explicitly approve any table scope, and separately approve database-wide sp_updatestats with SQL Server dbo/sysadmin permissions (db_owner membership alone is insufficient). Symptoms and reorganization do not trigger blanket updates. Statistic/histogram and plan changes have no universal automatic rollback. |
| Related constraint disabling | `sqlserver-schema/SKILL.md`, bulk-load foreign-key workflow | Preparation review identified missing local gates, subsequently corrected. Require exact-target DBA approval, table ALTER permission, dependency/availability checks, staging, maintenance and deliberate failure recovery. Keep normal writers stopped on load/validation failure, reconcile data with enforcement accounted for, and verify sys.foreign_keys.is_disabled = 0 AND is_not_trusted = 0 before resuming. WITH CHECK CHECK can fail. |
| Related backup/restore and KILL guidance | `sqlserver-backup/SKILL.md`, `sqlserver-monitoring/SKILL.md`, `scripts/blocking-analysis.sql`, `SECURITY.md` | Strengthen target/path/chain, tail-log, COPY_ONLY, restore rehearsal, session identity and rollback checks. Correct the claim that KILL immediately unblocks sessions. |
| Broad malicious-install or injection-free diagnosis | Builder is local file merging/ZIP only; baseline SECURITY says there is no injection surface | No evidence of malicious installation, persistence or exfiltration in the reviewed files. Reject the injection-free claim: catalog identifiers are data and feed dynamic SQL. Do not classify legitimate DBA functions themselves as malware. |

None of the four reported finding classes is already fixed or a false positive at
this baseline. Existing commented KILL examples were already guarded, but rollback
and session-reuse guidance needed correction. Do not infer hosted clearance from
local changes or the clean static report.

## Behavior and compatibility

The scripts still return recommendations; generated maintenance is never executed.
DROP output is `proposed_drop_statement`, now prefixed with `REVIEW-ONLY:` rather
than a line comment. The marker is intentionally non-SQL; a human DBA must prepare
a separate reviewed statement. Never remove markers in bulk or run a saved report
as a script, including through sqlcmd. Statistics proposals remain in the separate
`proposed_statistics_sql` column, for review rather than an automatic action queue.
Missing-index proposal names now use object/index-handle IDs and may need DBA
renaming/collision review. Column order is deterministic, equality before inequality;
the DBA must tune order within each group for the workload. Unused-index candidates
exclude primary keys, unique constraints and unique indexes, preserving integrity
independent of observed reads. Catalog visibility limits can yield NULL proposals.

SQL Server 2016+ and compatibility 130+ remain the documented floor. SQL Server
2022+ changes several DMV permissions; verify the specific DMV/version. ONLINE
support varies by edition, index and column types and does not eliminate locking.
CREATE proposals retain ONLINE = ON as online-only templates with an explicit
`execution_requirement` output column. EngineEdition alone cannot establish
eligibility; unsupported operations stop, with no automatic offline fallback.
Any offline alternative requires separate DBA approval and availability review.

The credential name changed from `SQL_PASSWORD` to `SQLCMDPASSWORD`. Operators must
update external secure provisioning; the examples do not copy or expose its value.
A nonempty exported password is required before SQL authentication can run. The root
Bash workflows reuse an explicitly selected authentication array; missing credentials
never select a different identity. Agents and automated processes never issue KILL,
even with approval. The human DBA preflight checks is_user_process = 1 and identity.

Missing-index proposals retain nvarchar(max) because valid lists can exceed 4000
characters. Use sqlcmd `-b -y 0 -w 65535`; do not combine `-W` with `-y` or `-Y`.
This removes the max-type display cap but does not make a formatted report a script;
very long rows still wrap, and unlimited display can increase output/network cost.
FOR XML TYPE cannot represent XML 1.0-invalid identifier characters such as U+0001.
On any query error, discard the entire report, including partial output, and stop
for DBA investigation. Do not filter/strip names or skip columns to manufacture SQL.

Separate monitoring permissions from change permissions; do not grant sysadmin as a shortcut.

All seven standalone skills and their existing relative references stay in place;
no runtime helper or new installation dependency is introduced. The canonical
builder still produces only `sql-server-skills/SKILL.md`, merging root plus seven
sub-skills. Its preexisting external script/reference links require the repository
for those supplemental files; this patch preserves that layout rather than changing
package semantics. The builder uses a Bash 3.2-compatible array loop and resolves
output paths before
entering its temporary directory. Relative paths refer to the caller's directory;
absolute paths remain supported, missing parents fail, and success requires an
actual nonempty archive. Git attributes apply export-ignore to docs/ and tests/,
in addition to existing publishing exclusions. Audit evidence and tests remain in
the repository for reviewers, outside the exported skill package. Root and generated
description scalars are quoted so their embedded colon parses as YAML.
No upstream CLI help dumps/fences exist in these source files; authored
SQL/shell examples were changed, not upstream help output.

## Offline validation

Requires Python 3 (standard library), Bash, Git and zip to exercise both builder
backends. Run from the repository; supply a disposable workspace scratch directory
and an existing artifact directory:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$SCRATCH_DIR" python3 -m unittest discover -s tests -v
TMPDIR="$SCRATCH_DIR" bash scripts/build-claude-skill.sh --output "$ARTIFACT_DIR/claude-skill.zip"
bash -n scripts/build-claude-skill.sh
git diff --check
```

For follow-up baseline proof, export each tracked file using `git show
dfbb8f6d158f5859f307c7e256b3bfdee54d622f:<path>` into a clean fixture, preserving files
that git archive would omit through export-ignore, then run the candidate tests
against that fixture. The earlier original-source audit used `8225232507b419ffbc8bafa19733bbf1cd9a0521`:

```bash
SECURITY_TEST_ROOT="$BASELINE_DIR" PYTHONDONTWRITEBYTECODE=1 TMPDIR="$SCRATCH_DIR" python3 -m unittest discover -s tests -v
```

The portable suite executes the actual builder with both zip and Python backends,
relative/absolute/space-containing paths and missing destinations. It verifies ZIP
contents against all eight skill bodies. A temporary Git repository exercises the
candidate export attributes and confirms package files remain available. No staging
of the working repository is required for that fixture.

Authored Bash examples run through a recording sqlcmd transport with synthetic
credentials and explicit integrated/SQL authentication choices. The checks cover
exact argv, nonzero status propagation, absent/empty/legacy-only password rejection
and missing authentication selection. A recording failure in the missing-index
step stops the complete monthly workflow without invoking subsequent diagnostics.
SQL expression fixtures cover quoted hostile
identifiers and a proposal exceeding 4000 characters. Comment-escape mutation tests
exercise the original `Then run: UPDATE STATISTICS` wording and other labels.
Source checks preserve the local statistics/constraint gates and each KILL preflight.

**These are source/fixture checks, not SQL Server execution.** SQLite evaluates only
extracted concatenations with modeled QUOTENAME/catalog functions; it does not model
SQL Server types, parser, DMV permissions, XML aggregation or sqlcmd output rendering.
Python XML fixtures show that U+0001 and other invalid characters survive quoting
and fail an XML parser; they do not establish a SQL Server engine result. No safe
engine or sqlcmd binary was available for this follow-up. A disposable SQL Server
2016+ instance and a real sqlcmd client are still needed to validate long max-typed
results, XML failure status, and the review marker's parser behavior. Do not infer
those results from the offline suite. No destructive SQL, production credentials,
or database/cloud mutations were used. Local tests do not establish hosted scan
clearance; that requires a future approved publication and scan.

## Preparation and delivered review scope

The initial preparation environment could not complete live issue/PR lookups. Two
preparation review cycles also found incomplete statistics and constraint safeguards;
those findings were corrected before the initial delivery. These are historical
preparation limitations, not outstanding delivery failures.

[PR #2](https://github.com/vince-winkintel/sql-server-skills/pull/2) records the delivered
security patch. Its retained delivery record reports an independent final review,
Victor's rerun of the 13-test suite and canonical build, and live issue/thread/default-
branch checks before delivery. The retained PR snapshot at the start of this follow-up
was open and mergeable, with no configured checks observed; this is not a claim that
CI ran or a claim about future PR state. The follow-up review identified the client
output, export, review-marker, XML-limit, KILL, credential, ONLINE, audit, mutation-test
and relative-output issues addressed by this record. The commands above are locally
rerunnable evidence; preparation worker paths and pipeline TODOs are not dependencies
of this repository's documentation. Proposed version remains **1.0.1**.

## Semantic references

Checked against Microsoft documentation on 2026-10-30:

- [sqlcmd authentication](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility)
- [QUOTENAME](https://learn.microsoft.com/en-us/sql/t-sql/functions/quotename-transact-sql)
- [Missing index columns](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-missing-index-columns-transact-sql)
- [ALTER INDEX](https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-index-transact-sql)
- [DBCC FREEPROCCACHE](https://learn.microsoft.com/en-us/sql/t-sql/database-console-commands/dbcc-freeproccache-transact-sql)
- [KILL](https://learn.microsoft.com/en-us/sql/t-sql/language-elements/kill-transact-sql)
- [RESTORE permissions](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-transact-sql)
- [VERIFYONLY limits](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-verifyonly-transact-sql)
- [Recovery model changes](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/view-or-change-the-recovery-model-of-a-database-sql-server)
- [COPY_ONLY](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/copy-only-backups-sql-server)

Additional operational references checked before initial delivery:
[UPDATE STATISTICS](https://learn.microsoft.com/en-us/sql/t-sql/statements/update-statistics-transact-sql),
[sp_updatestats](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-updatestats-transact-sql),
and [foreign-key disabling and trust](https://learn.microsoft.com/en-us/sql/relational-databases/tables/disable-foreign-key-constraints-with-insert-and-update-statements).

Follow-up semantic checks on 2026-10-30 used Microsoft's documentation for
[sqlcmd display widths, password prompting and -b](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility),
[FOR XML invalid characters](https://learn.microsoft.com/en-us/sql/relational-databases/xml/invalid-characters-and-escape-rules),
[online index restrictions](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/guidelines-for-online-index-operations),
and [session is_user_process](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-sessions-transact-sql).
These references establish documented semantics, not engine execution of these scripts.

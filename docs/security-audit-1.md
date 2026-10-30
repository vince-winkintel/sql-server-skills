# Security audit #1 — patch 1.0.1 preparation

Prepared 2026-10-30 for [issue #1](https://github.com/vince-winkintel/sql-server-skills/issues/1).
Proposed next immutable version: **1.0.1**, unreleased. The repository has only the
`v1.0.0` tag and no tracked package/version manifest; the retained registry manifest
reports one version, `1.0.0`. Preserve this tag-based release convention; do not
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
| Related recommendation SQL | `scripts/{missing-indexes,index-fragmentation,unused-indexes}.sql` and `sqlserver-indexes/SKILL.md` | Confirmed same class. Quote components and individual missing-index columns from sys.dm_db_missing_index_columns, use Unicode expressions and short numeric index names, and require exact-target DBA review. XML TYPE/value avoids entity corruption without parsing comma-separated names. |
| Comment-context escape | DROP and statistics recommendations prepend a line comment to catalog names | Independently found during review. CR/LF survives QUOTENAME and can end a comment. Return DROP and statistics proposals in separate columns with no names embedded in comments. Include CR, LF and CRLF fixtures. |
| SQP-2 broad cache eviction | `sqlserver-execution-plans/SKILL.md:272–273` | Confirmed warning gap. Retain commented reference only; prefer procedure/query or verified-plan scope. Explain instance-wide impact, permission, recompilation cost and lack of cache rollback. This is disruption risk, not deletion of stored user data. |
| SQP-2 destructive schema guidance | `sqlserver-schema/SKILL.md:93–100,154–156` | Confirmed warning gap. Add adjacent DBA, dependencies, backup/recovery, staging and deprecation checks for DROP/rename. Existence guards do not establish safety. |
| Related statistics maintenance | `sqlserver-execution-plans/SKILL.md`, `sqlserver-query-optimization/SKILL.md`, `sqlserver-execution-plans/references/plan-operators.md`, `sqlserver-indexes/SKILL.md`, `scripts/index-fragmentation.sql` | Independent review found incomplete propagation. All authored workflow copies now require local exact-target DBA approval, table ALTER permission, workload/recompilation/tempdb review, staging, maintenance, stop criteria and recovery planning. Preserve read-only inspection; prefer a reviewed named statistic, explicitly approve any table scope, and separately approve database-wide sp_updatestats with SQL Server dbo/sysadmin permissions (db_owner membership alone is insufficient). Symptoms and reorganization do not trigger blanket updates. Statistic/histogram and plan changes have no universal automatic rollback. |
| Related constraint disabling | `sqlserver-schema/SKILL.md`, bulk-load foreign-key workflow | Failed independent review identified missing local gates. Require exact-target DBA approval, table ALTER permission, dependency/availability checks, staging, maintenance and deliberate failure recovery. Keep normal writers stopped on load/validation failure, reconcile data with enforcement accounted for, and verify sys.foreign_keys.is_disabled = 0 AND is_not_trusted = 0 before resuming. WITH CHECK CHECK can fail. |
| Related backup/restore and KILL guidance | `sqlserver-backup/SKILL.md`, `sqlserver-monitoring/SKILL.md`, `scripts/blocking-analysis.sql`, `SECURITY.md` | Strengthen target/path/chain, tail-log, COPY_ONLY, restore rehearsal, session identity and rollback checks. Correct the claim that KILL immediately unblocks sessions. |
| Broad malicious-install or injection-free diagnosis | Builder is local file merging/ZIP only; baseline SECURITY says there is no injection surface | No evidence of malicious installation, persistence or exfiltration in the reviewed files. Reject the injection-free claim: catalog identifiers are data and feed dynamic SQL. Do not classify legitimate DBA functions themselves as malware. |

None of the four reported finding classes is already fixed or a false positive at
this baseline. Existing commented KILL examples were already guarded, but rollback
and session-reuse guidance needed correction. Do not infer hosted clearance from
local changes or the clean static report.

## Behavior and compatibility

The scripts still return recommendations; generated maintenance is never executed.
DROP output is now `proposed_drop_statement` (formerly commented DROP output);
statistics guidance is now a separate `proposed_statistics_sql` column. These are
SQL text for DBA review, not inert comments and never an automatic action queue.
Missing-index proposal names now use object/index-handle IDs and may need DBA
renaming/collision review. Column order is deterministic, equality before inequality;
the DBA must tune order within each group for the workload. Unused-index candidates
exclude primary keys, unique constraints and unique indexes, preserving integrity
independent of observed reads. Catalog visibility limits can yield NULL proposals.

SQL Server 2016+ and compatibility 130+ remain the documented floor. SQL Server
2022+ changes several DMV permissions; verify the specific DMV/version. ONLINE
support varies by edition and index type and does not eliminate locking. Separate
monitoring permissions from change permissions; do not grant sysadmin as a shortcut.

All seven standalone skills and their existing relative references stay in place;
no runtime helper or new installation dependency is introduced. The canonical
builder still produces only `sql-server-skills/SKILL.md`, merging root plus seven
sub-skills. Its preexisting external script/reference links require the repository
for those supplemental files; this patch preserves that layout rather than changing
package semantics. The only shell change replaces mapfile with a Bash 3.2-compatible
array loop. No upstream CLI help dumps/fences exist in these source files; authored
SQL/shell examples were changed, not upstream help output.

## Offline validation

Requires Python 3 (standard library), Bash and the builder's existing zip/Python
fallback. Run from the repository; supply a disposable workspace scratch directory:

```bash
TMPDIR="$SCRATCH_DIR" python3 -m unittest discover -s tests -v
TMPDIR="$SCRATCH_DIR" bash scripts/build-claude-skill.sh --output "$ARTIFACT_DIR/claude-skill.zip"
bash -n scripts/build-claude-skill.sh
git diff --check
```

For baseline proof, export each tracked file using `git show
8225232507b419ffbc8bafa19733bbf1cd9a0521:<path>` into a clean fixture, preserving files
that git archive would omit through export-ignore, then run the candidate tests:

```bash
SECURITY_TEST_ROOT="$BASELINE_DIR" TMPDIR="$SCRATCH_DIR" python3 -m unittest discover -s tests -v
```

Regression slices were run RED then GREEN for authentication argv, identifiers,
operational guidance, Bash 3.2 building, uniqueness guards and comment-context
escaping. Tests execute actual authored shell examples with a recording sqlcmd
transport and assert exact argv. SQL tests extract authored expressions and evaluate
them in SQLite with modeled QUOTENAME/catalog functions; source checks cover XML
list assembly, safety text and non-execution. Fixtures cover brackets, semicolons,
quotes, Unicode, spaces, keywords, comma/XML characters and CR/LF/CRLF. Builder tests
execute the actual script and compare all eight source bodies with the ZIP output.

**These are source/fixture checks, not SQL Server execution.** No safe engine was
provided, so T-SQL parsing, DMV availability/permissions, XML aggregation behavior,
execution plans and live operational safety remain unverified. No destructive SQL,
production credentials or database/cloud mutations were used. Tests and logs do not
establish hosted scan clearance; that requires a future approved publication and scan.
Public issue/thread and API lookups were unavailable via the browsing tool; retained
issue/open-PR evidence and three public keyword searches were checked. Victor must
refresh live issue/PR/version state before publishing.

The original eight-test suite passed on the candidate; on both baseline and
published fixtures it exited 1 with 23 assertion/subtest failures. The narrow fix
pass added two workflow-local source contract tests: both failed before the Markdown
fixes and passed afterward. The expanded ten-test candidate suite also checks both
corrected workflows in the canonical merged ZIP. These are offline contract checks,
not live permission, validation or recovery tests.
Bash syntax, diff whitespace checks, canonical build and final ZIP inspection pass.
Fix-pass commands and results are recorded in `workers/sql-server-skills/fix-pass-1.json`.
Final verification cycle 2 added three actual-copy regressions and a section-bounded
assertion for Statistics Management in the canonical merged SKILL. Before the fix,
the thirteen-test suite had four expected failures: optimization, plan-operator and
index-script workflow gates, plus the canonical bundle's optimization section.
After propagation, all thirteen tests pass. The search of all authored Markdown/SQL
copies also covered post-reorganize advice and its generated table-wide proposals;
the index skill's actual section is checked in both source and merged output.
These documentation contracts cannot establish SQL Server operational safety.
Cycle-2 logs, the local ZIP, diff and `fix-pass-2.json` are retained only under
`workers/sql-server-skills/`, outside Git. Proposed version remains **1.0.1**.
The prior review failed; the parent must regenerate the candidate snapshot and obtain
independent re-review. No earlier approval applies to this changed candidate.

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

Additional references cited by the failed review for the narrow fix pass:
[UPDATE STATISTICS](https://learn.microsoft.com/en-us/sql/t-sql/statements/update-statistics-transact-sql),
[sp_updatestats](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-updatestats-transact-sql),
and [foreign-key disabling and trust](https://learn.microsoft.com/en-us/sql/relational-databases/tables/disable-foreign-key-constraints-with-insert-and-update-statements).
Fix pass 1 used the supplied review's source-backed findings without refetching
those pages under its network restriction. Cycle 2 used the explicitly permitted
public read-only documentation access to verify UPDATE STATISTICS and sp_updatestats:
table ALTER versus SQL Server dbo/sysadmin permissions, FULLSCAN and default sampling,
table/database scope, recompilation and tempdb costs. The foreign-key page was not
refetched in cycle 2; that workflow was outside this propagation fix.

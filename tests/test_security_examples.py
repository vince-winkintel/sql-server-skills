"""Offline checks of authored examples; never connect to SQL Server.

SECURITY_TEST_ROOT allows these tests to inspect a clean baseline export.
Set TMPDIR to a disposable directory when running the builder tests.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sqlite3
import unittest
import tempfile
import zipfile

ROOT = Path(os.environ.get('SECURITY_TEST_ROOT', Path(__file__).resolve().parents[1]))


def read(name):
    return (ROOT / name).read_text(encoding='utf-8')


INDEX_FILES = ('scripts/index-fragmentation.sql', 'scripts/unused-indexes.sql',
               'sqlserver-indexes/SKILL.md', 'sqlserver-indexes/references/index-strategies.md')
CASES = ('close]bracket', 'x]; DROP TABLE victim;--', "O'Brien", '資料Δ', 'two words', 'SELECT', 'line\nDROP TABLE victim;--', 'carriage\rreturn', 'both\r\nnewlines')


def evaluate_expression(expression, name):
    """Evaluate the authored concatenation with fixture-only SQL function semantics.

    SQLite is only an expression harness, NOT SQL Server syntax/engine validation.
    QUOTENAME's documented bracket escaping is modeled, never sent to a server.
    """
    connection = sqlite3.connect(':memory:')
    connection.create_function('QUOTENAME', 1, lambda x: '[' + str(x).replace(']', ']]') + ']')
    connection.create_function('DB_NAME', -1, lambda *args: 'db_' + name)
    connection.create_function('OBJECT_SCHEMA_NAME', -1, lambda *args: 'schema_' + name)
    connection.create_function('OBJECT_NAME', -1, lambda *args: 'table_' + name)
    # Translate only this documented expression subset; no full T-SQL emulation.
    expression = re.sub(r"\bN(?=')", '', expression)
    expression = re.sub(r'CONVERT\(nvarchar\(11\), (mid\.\w+)\)', r'CAST(\1 AS TEXT)', expression, flags=re.I)
    bindings = {'i.name': 'index_' + name, 's.name': 'schema_' + name,
                'o.name': 'table_' + name, 'c.column_name': name,
                'mid.object_id': 42, 'mid.index_handle': 7, 'mid.database_id': 9}
    for index, (token, value) in enumerate(bindings.items()):
        expression = expression.replace(token, ':p' + str(index))
    # Plus signs in literals would require a real parser. Fixtures enter as bindings.
    expression = expression.replace(' + ', ' || ')
    try:
        return connection.execute('SELECT ' + expression, {'p' + str(i): v for i, v in enumerate(bindings.values())}).fetchone()[0]
    finally:
        connection.close()


class SecurityExamples(unittest.TestCase):
    def test_sqlcmd_argv(self):
        # The real shell examples run with only the sqlcmd transport replaced.
        # Its recorder emits argv only, never its environment.
        env = {'PATH': os.environ['PATH'], 'SQL_SERVER': 'fixture server',
               'SQL_DATABASE': 'fixture database', 'SQL_USER': 'fixture user',
               'SQLCMDPASSWORD': 'synthetic-secret', 'SQL_PASSWORD': 'synthetic-secret'}
        recorder = '''sqlcmd() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@"; };\n'''
        count = 0
        for name in ('SKILL.md', 'README.md', 'SECURITY.md'):
            for command in re.findall(r'^sqlcmd .*$', read(name).replace('\\\n', ''), re.M):
                with self.subTest(file=name, command=command):
                    result = subprocess.run(['bash', '-c', recorder + command], env=env,
                                            text=True, capture_output=True, check=True)
                    argv = json.loads(result.stdout)
                    self.assertNotIn('-P', argv)
                    self.assertNotIn('synthetic-secret', result.stdout + result.stderr)
                    expected = ['-S', 'fixture server']
                    if '-U' in argv:
                        expected += ['-U', 'fixture user']
                    else:
                        expected += ['-E']
                    if '-d' in argv:
                        expected += ['-d', 'fixture database' if '$SQL_DATABASE' in command else 'master']
                    if '-i' in argv:
                        script = re.search(r'-i (\S+)', command).group(1)
                        self.assertTrue((ROOT / script).is_file(), script)
                        expected += ['-i', script]
                    if '-o' in argv:
                        expected += ['-o', 'results.txt', '-s', ',', '-W']
                    self.assertEqual(argv, expected)
                    count += 1
        self.assertGreaterEqual(count, 15)
        for path in (ROOT / 'scripts').glob('*.sql'):
            self.assertNotRegex(path.read_text(), r'\bsqlcmd[^\n]*\s-P\b')
        self.assertNotIn('name: SQL_PASSWORD', read('SKILL.md'))

    def test_generated_identifiers(self):
        for filename in INDEX_FILES:
            source = read(filename)
            self.assertNotRegex(source, r'(?im)^\s*EXEC(?:UTE)?\s+(?:sys\.)?sp_executesql')
            expressions = re.findall(r"N?'(?:ALTER|-- DROP|DROP) INDEX .*?N?'(?: REBUILD[^']*;| REORGANIZE;|;)'", source, re.S)
            self.assertTrue(expressions, filename)
            for expression in expressions:
                for token in ('i.name', 's.name', 'o.name'):
                    self.assertIn('QUOTENAME(' + token + ')', expression, filename)
                self.assertIn('QUOTENAME(DB_NAME())', expression, filename)
                for name in CASES:
                    with self.subTest(file=filename, name=name):
                        quote = lambda prefix: '[' + (prefix + name).replace(']', ']]') + ']'
                        action = ('-- DROP' if '-- DROP' in expression else 'DROP') if 'DROP' in expression else 'ALTER'
                        suffix = expression.rsplit("'", 2)[1]
                        expected = action + ' INDEX ' + quote('index_') + ' ON ' + '.'.join(quote(x) for x in ('db_', 'schema_', 'table_'))
                        self.assertEqual(evaluate_expression(expression, name), expected + suffix)

    def test_statistics_proposals(self):
        for filename in ('scripts/index-fragmentation.sql', 'sqlserver-indexes/SKILL.md'):
            match = re.search(r"N'UPDATE STATISTICS '.*?\+ N';'", read(filename), re.S)
            self.assertIsNotNone(match)
            for name in CASES:
                quote = lambda prefix: '[' + (prefix + name).replace(']', ']]') + ']'
                self.assertEqual(evaluate_expression(match.group(), name),
                                 'UPDATE STATISTICS ' + '.'.join(quote(x) for x in ('db_', 'schema_', 'table_')) + ';')

    def test_missing_index_identifiers(self):
        for filename in ('scripts/missing-indexes.sql', 'sqlserver-indexes/SKILL.md'):
            source = read(filename)
            match = re.search(r"N'CREATE NONCLUSTERED INDEX '(.*?)\+ N' \('", source, re.S)
            self.assertIsNotNone(match, filename)
            expression = "N'CREATE NONCLUSTERED INDEX '" + match.group(1)
            self.assertIn('QUOTENAME(DB_NAME(mid.database_id))', expression)
            self.assertIn('QUOTENAME(OBJECT_SCHEMA_NAME(mid.object_id, mid.database_id))', expression)
            self.assertIn('QUOTENAME(OBJECT_NAME(mid.object_id, mid.database_id))', expression)
            for name in CASES:
                quote = lambda prefix: '[' + (prefix + name).replace(']', ']]') + ']'
                self.assertEqual(evaluate_expression(expression.strip(), name),
                                 'CREATE NONCLUSTERED INDEX [IX_missing_42_7] ON ' +
                                 '.'.join(quote(x) for x in ('db_', 'schema_', 'table_')))
            # Column lists are reconstructed from individual names, never parsed by commas.
            columns = re.findall(r"N', ' \+ QUOTENAME\(c.column_name\)", source)
            self.assertEqual(len(columns), 2)
            for expression in columns:
                for name in CASES + ('comma,column', 'amp&less<greater>'):
                    self.assertEqual(evaluate_expression(expression, name), ', [' + name.replace(']', ']]') + ']')
            self.assertEqual(source.count('sys.dm_db_missing_index_columns(mid.index_handle)'), 2)
            self.assertEqual(source.count("FOR XML PATH(N''), TYPE"), 2)
            self.assertEqual(source.count(".value(N'.', N'nvarchar(max)')"), 2)
            self.assertNotRegex(source, r"\+\s*mid\.(?:statement|equality_columns|inequality_columns|included_columns)")

    def test_operational_review_boundaries(self):
        # Documentation contract checks, not SQL execution or proof of safe operations.
        plans = read('sqlserver-execution-plans/SKILL.md')
        self.assertNotRegex(plans, r'(?m)^DBCC FREEPROCCACHE\s*;')
        for phrase in ('instance-wide', 'ALTER SERVER STATE', 'plan_handle', 'sp_recompile', 'cannot be rolled back'):
            self.assertIn(phrase, plans)
        schema = read('sqlserver-schema/SKILL.md')
        for statement in ('ALTER TABLE dbo.Customers DROP COLUMN', 'ALTER TABLE dbo.Customers DROP CONSTRAINT', 'DROP PROCEDURE dbo.usp_OldProcedure'):
            before = schema[:schema.index(statement)][-650:]
            for phrase in ('DBA', 'dependencies', 'staging', 'recovery'):
                self.assertIn(phrase, before)
        backup = read('sqlserver-backup/SKILL.md')
        for phrase in ('exact-target DBA review', 'COPY_ONLY', 'tail-log', 'does not replace a test restore', 'FILELISTONLY', 'least privilege'):
            self.assertIn(phrase, backup)
        for filename in ('scripts/blocking-analysis.sql', 'sqlserver-monitoring/SKILL.md', 'SECURITY.md'):
            source = read(filename)
            for phrase in ('session IDs can be reused', 'STATUSONLY', 'rollback can take'):
                self.assertIn(phrase, source, filename)
        for filename in INDEX_FILES + ('scripts/missing-indexes.sql',):
            source = read(filename)
            for phrase in ('exact-target DBA review', 'least privilege', 'staging', 'recovery'):
                self.assertIn(phrase, source, filename)
        self.assertNotIn('There is no SQL injection surface', read('SECURITY.md'))

    def test_generated_names_never_enter_line_comments(self):
        # QUOTENAME preserves CR/LF: SQL comments are not a safe identifier context.
        for filename in INDEX_FILES:
            source = read(filename)
            with self.subTest(file=filename):
                self.assertNotRegex(source, r"N?'-- DROP INDEX.*?QUOTENAME")
                self.assertNotIn('Then review: UPDATE STATISTICS', source)

    def assert_statistics_workflow(self, source):
        # Restrict checks to the actual workflow, not unrelated cache warnings.
        workflow = source.split('**Update statistics:**', 1)[1].split('\n---', 1)[0]
        before = workflow.split('UPDATE STATISTICS dbo.Orders', 1)[0]
        for phrase in ('exact-target DBA approval', 'database, schema, table and statistic',
                       'ALTER on the target table', 'workload', 'recompilation',
                       'staging', 'maintenance window', 'recovery', 'histogram',
                       'cannot automatically undo', 'restore the plan cache'):
            self.assertIn(phrase, before)
        # A named statistic is the reviewed example; no active database-wide default.
        self.assertIn('-- UPDATE STATISTICS dbo.Orders [ReviewedStatisticName] WITH FULLSCAN;', workflow)
        self.assertNotRegex(workflow, r'(?m)^\s*(?:UPDATE STATISTICS|EXEC(?:UTE)?\s+(?:sys\.)?sp_updatestats)\b')
        broad = workflow.split('-- EXEC sys.sp_updatestats;', 1)
        self.assertEqual(len(broad), 2)
        for phrase in ('not a default', 'database-wide', 'dbo', 'sysadmin',
                       'db_owner membership alone', 'separate DBA approval'):
            self.assertIn(phrase, broad[0][-850:])
        self.assertIn("s.object_id = OBJECT_ID(N'dbo.Orders', N'U')", workflow)

    def test_statistics_update_workflow_gates(self):
        self.assert_statistics_workflow(read('sqlserver-execution-plans/SKILL.md'))

    def assert_local_statistics_gates(self, workflow):
        # Offline documentation contract only, not permission or recovery execution.
        # Removing gates from any actual copy must fail even if another copy is safe.
        for phrase in ('exact-target DBA approval', 'database, schema, table and statistic',
                       'ALTER on the target table', 'workload', 'recompilation',
                       'tempdb', 'staging', 'maintenance window', 'histogram',
                       'stop', 'recovery', 'no universal rollback'):
            self.assertIn(phrase, workflow)
        self.assertNotRegex(workflow, r'(?m)^\s*(?:UPDATE STATISTICS|EXEC(?:UTE)?\s+(?:sys\.)?sp_updatestats)\b')

    def assert_optimization_statistics_workflow(self, source):
        # Bound the merged-bundle assertion to THIS section, not execution-plan text.
        workflow = source.split('## Statistics Management', 1)[1].split('\n---', 1)[0]
        before = workflow.split('-- UPDATE STATISTICS', 1)[0]
        self.assert_local_statistics_gates(before)
        self.assert_local_statistics_gates(workflow)
        self.assertIn('-- UPDATE STATISTICS dbo.Orders [ReviewedStatisticName] WITH FULLSCAN;', workflow)
        broad = workflow.split('-- EXEC sys.sp_updatestats;', 1)
        self.assertEqual(len(broad), 2)
        for phrase in ('not a default', 'database-wide', 'separate DBA approval',
                       'dbo', 'sysadmin', 'db_owner membership alone'):
            self.assertIn(phrase, broad[0][-850:])
        for inspection in ('FROM sys.databases', 'WHERE name = DB_NAME()',
                           "DBCC SHOW_STATISTICS ('dbo.Orders', 'IX_Orders_CustomerID')"):
            self.assertIn(inspection, workflow)
        self.assertNotIn('**When to run manually:**', workflow)

    def test_optimization_statistics_mirror_gates(self):
        self.assert_optimization_statistics_workflow(read('sqlserver-query-optimization/SKILL.md'))

    def test_plan_operator_statistics_mirror_gates(self):
        workflow = read('sqlserver-execution-plans/references/plan-operators.md').split('## Spill Warnings', 1)[1].split('\n---', 1)[0]
        self.assert_local_statistics_gates(workflow.split('-- UPDATE STATISTICS', 1)[0])
        self.assert_local_statistics_gates(workflow)
        self.assertIn('-- UPDATE STATISTICS dbo.Orders [ReviewedStatisticName] WITH FULLSCAN;', workflow)
        self.assertNotIn('large discrepancy = stale stats', workflow)
        self.assertNotIn('Run `UPDATE STATISTICS', workflow)

    def assert_index_statistics_workflow(self, workflow):
        # Both the SQL generator and its authored Markdown mirror need local gates.
        self.assert_local_statistics_gates(workflow.split("N'UPDATE STATISTICS '", 1)[0])
        self.assertNotIn('run `UPDATE STATISTICS` separately', workflow)
        self.assertNotIn('Run this after a REORGANIZE pass', workflow)
        self.assertIn('proposed_statistics_sql', workflow)

    def test_index_statistics_mirror_gates(self):
        self.assert_index_statistics_workflow(read('scripts/index-fragmentation.sql'))
        workflow = read('sqlserver-indexes/SKILL.md').split('## 2. Index Fragmentation', 1)[1].split('## 3. Unused Indexes', 1)[0]
        self.assert_index_statistics_workflow(workflow)

    def assert_constraint_workflow(self, source):
        workflow = source.split('## Foreign Key Patterns', 1)[1].split('## Computed Columns', 1)[0]
        before = workflow.split('ALTER TABLE dbo.OrderItems NOCHECK', 1)[0][-1800:]
        for phrase in ('exact-target DBA approval', 'database, schema, table and constraint',
                       'ALTER on the target table', 'dependencies', 'availability',
                       'staging', 'maintenance window', 'recovery', 'normal writes',
                       'inserts and updates', 'enforcement'):
            self.assertIn(phrase, before)
        self.assertIn('-- ALTER TABLE dbo.OrderItems NOCHECK CONSTRAINT FK_OrderItems_Orders;', workflow)
        self.assertNotRegex(workflow, r'(?m)^\s*ALTER TABLE.*\bNOCHECK\b')
        after = workflow.split('NOCHECK CONSTRAINT FK_OrderItems_Orders;', 1)[1]
        for phrase in ('not guaranteed', 'stop', 'reconcile', 'enforcement', 'normal writes'):
            self.assertIn(phrase, after)
        self.assertIn('WITH CHECK CHECK CONSTRAINT FK_OrderItems_Orders;', after)
        # Inspect the actual fail-closed catalog guard, not fixture SQL execution.
        guard = re.search(r'IF NOT EXISTS\s*\((.*?)\)\s*THROW\s+\d+,', after, re.S)
        self.assertIsNotNone(guard)
        for clause in ('FROM sys.foreign_keys',
                       "parent_object_id = OBJECT_ID(N'dbo.OrderItems', N'U')",
                       "name = N'FK_OrderItems_Orders'", 'is_disabled = 0', 'is_not_trusted = 0'):
            self.assertIn(clause, guard.group(1))
        self.assertLess(after.index('WITH CHECK CHECK'), after.index('IF NOT EXISTS'))

    def test_constraint_disable_workflow_gates(self):
        self.assert_constraint_workflow(read('sqlserver-schema/SKILL.md'))


    def test_unused_index_preserves_integrity(self):
        for filename in ('scripts/unused-indexes.sql', 'sqlserver-indexes/SKILL.md'):
            source = read(filename)
            for condition in ("i.type_desc = 'NONCLUSTERED'", 'i.is_primary_key = 0',
                              'i.is_unique_constraint = 0', 'i.is_unique = 0'):
                self.assertIn(condition, source, filename)


    def test_canonical_builder(self):
        with tempfile.TemporaryDirectory(prefix='sql-skills-build-') as temporary:
            output = Path(temporary) / 'claude-skill.zip'
            result = subprocess.run(['bash', str(ROOT / 'scripts/build-claude-skill.sh'),
                                     '--root', str(ROOT), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(output) as archive:
                files = [n for n in archive.namelist() if not n.endswith('/')]
                self.assertEqual(files, ['sql-server-skills/SKILL.md'])
                merged = archive.read(files[0]).decode('utf-8')
            for source in [ROOT / 'SKILL.md', *sorted(ROOT.glob('sqlserver-*/SKILL.md'))]:
                body = source.read_text().split('---', 2)[2].strip()
                self.assertIn(body, merged, str(source))
            self.assertNotRegex(merged, r'(?m)^sqlcmd[^\n]*\s-P\b')
            self.assertIn('QUOTENAME(i.name)', merged)
            self.assertNotRegex(merged, r'(?m)^DBCC FREEPROCCACHE;')
            self.assert_statistics_workflow(merged)
            self.assert_optimization_statistics_workflow(merged)
            self.assert_index_statistics_workflow(merged.split('## 2. Index Fragmentation', 1)[1].split('## 3. Unused Indexes', 1)[0])
            self.assert_constraint_workflow(merged)


if __name__ == '__main__':
    unittest.main()

"""Shared TEKS normalization/catalog tests; source values are synthetic only."""

from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from aware_results.errors import PipelineError
from aware_results.export import build_packet
from aware_results.migrate import migrate_store
from aware_results.standards import canonical_code, normalize_standard, standard_sort_key
from aware_results.storage import canonical_json, connect, digest, import_report, initialize_store, read_generation
from synthetic_xlsx import PRIVATE_MARKERS, items, students


CONTEXT = {'source_namespace':'SYNTHETIC_SCOPE','assessment_ref':'SYNTHETIC_ASSESSMENT','population_ref':'SYNTHETIC_POPULATION','framework_ref':'SYNTHETIC_TEKS_SUBJECT_VERSION'}
STUDENT = 'student_learning_standards'
GROUP = 'group_item_analysis'


class StandardsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base/'work'
        initialize_store(self.work)

    def ingest(self, spec, method, context=None):
        source=self.base/'synthetic.xlsx'
        spec.save(source)
        return import_report(self.work,source,method,context or CONTEXT)[0]

    def test_two_notations_share_structured_canonical_code(self):
        left=normalize_standard('5.2(B.v) [S]')
        right=normalize_standard('5.2.B.v')
        self.assertEqual(left.code,right.code)
        self.assertEqual((left.grade,left.knowledge_skill_number,left.student_expectation,left.subexpectation),(5,2,'B','v'))
        self.assertEqual(left.source_label,'5.2(B.v) [S]')
        self.assertEqual(left.source_tag,'S')
        self.assertIsNone(right.source_tag)

    def test_case_padding_and_subexpectation_preservation(self):
        self.assertEqual(normalize_standard('05.02(b.V) [s]').code,'5.2.B.v')
        self.assertEqual(normalize_standard('05.02(b.V) [s]').source_tag,'s')
        self.assertEqual(normalize_standard('6.8.e.III').code,'6.8.E.iii')
        self.assertNotEqual(normalize_standard('5.2.B').code,normalize_standard('5.2.B.v').code)
        self.assertNotEqual(normalize_standard('5.8.C').code,normalize_standard('6.8.C').code)
        with self.assertRaisesRegex(PipelineError,'^noncanonical_standard_code$'):
            canonical_code('05.2.B.V')

    def test_unknown_labels_stop_without_echoing_the_input(self):
        for label in ('SYNTHETIC_PRIVATE_NAME','5.2(B.v) [X]','5.2.B.v;PRIVATE','5.0.A','5.2'):
            with self.subTest(label=label):
                with self.assertRaisesRegex(PipelineError,'^standard_label_unrecognized$'):
                    normalize_standard(label)

    def test_numeric_and_roman_sorting(self):
        codes=['5.10.A','5.2.B.x','5.2.B.ix','5.2.B.ii','5.2.B.i','6.2.B','5.2.B']
        self.assertEqual(sorted(codes,key=standard_sort_key),['5.2.B','5.2.B.i','5.2.B.ii','5.2.B.ix','5.2.B.x','5.10.A','6.2.B'])

    def test_retained_structural_labels_normalize_without_changing_known_codes(self):
        for path in (ROOT/'templates/observations').glob('*.json'):
            observation=json.loads(path.read_text(encoding='utf-8'))
            labels=observation.get('standard_headers',{}).values() or observation['standard_codes']
            self.assertEqual({normalize_standard(label).code for label in labels},set(observation['standard_codes']))

    def test_both_report_families_reuse_one_catalog_entry_and_keep_original_labels(self):
        student=students(2); student.put('F3','5.2(B.v) [S]')
        group=items(3); group.put('D3','5.2.B.v')
        first=self.ingest(student,STUDENT)
        second=self.ingest(group,GROUP)
        connection=connect(self.work)
        try:
            entries=connection.execute("SELECT * FROM standards WHERE standard_code='5.2.B.v'").fetchall()
            self.assertEqual(len(entries),1)
            standard=entries[0]
            self.assertEqual((standard['grade'],standard['knowledge_skill_number'],standard['student_expectation'],standard['subexpectation']),(5,2,'B','v'))
            self.assertIsNone(standard['description'])
            labels=connection.execute('SELECT source_label,source_tag FROM standard_source_labels WHERE standard_key=? ORDER BY source_label',(standard['standard_key'],)).fetchall()
            self.assertEqual([tuple(row) for row in labels],[('5.2(B.v) [S]','S'),('5.2.B.v',None)])
            self.assertEqual(build_packet(connection,first)['standards_scope_key'],build_packet(connection,second)['standards_scope_key'])
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:
            connection.close()

    def test_different_frameworks_do_not_merge_identical_short_codes(self):
        first=self.ingest(students(2),STUDENT)
        group=items(3); group.put('E3',0.25,2)
        second=self.ingest(group,GROUP,{**CONTEXT,'assessment_ref':'SYNTHETIC_OTHER_SUBJECT_TEST','framework_ref':'SYNTHETIC_OTHER_SUBJECT_VERSION'})
        connection=connect(self.work)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM standards WHERE standard_code='7.1.A.i'").fetchone()[0],2)
            self.assertNotEqual(build_packet(connection,first)['standards_scope_key'],build_packet(connection,second)['standards_scope_key'])
        finally:
            connection.close()

    def test_duplicate_normalized_header_variants_are_rejected(self):
        spec=students(2); spec.put('G3','07.01(A.I) [S]')
        with self.assertRaisesRegex(PipelineError,'^duplicate_standard$'):
            self.ingest(spec,STUDENT)

    def test_export_natural_order_keeps_values_under_the_right_standard(self):
        snapshot=self.ingest(students(12),STUDENT)
        connection=connect(self.work)
        try:
            packet=build_packet(connection,snapshot)
        finally:
            connection.close()
        table=packet['tables']['students']
        self.assertEqual(table['columns'][4:],[f'std:7.{i}.A.i' for i in range(1,13)])
        first=next(row for row in table['rows'] if row[1]==10.5)
        self.assertEqual(first[4:], [0,0.625,None]*4)

    def test_foreign_key_prevents_different_code_for_same_catalog_entry(self):
        self.ingest(items(3),GROUP)
        connection=connect(self.work)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE group_item_results SET standard_code='7.99.A.i' WHERE question_label='1'")
        finally:
            connection.close()


class LegacyCatalogMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve()
        self.work=self.base/'legacy'
        (self.work/'originals').mkdir(parents=True)
        self.student_source=self.base/'synthetic-student.xlsx'
        self.group_source=self.base/'synthetic-group.xlsx'
        students(2).save(self.student_source); items(3).save(self.group_source)
        self.student_snapshot='r_'+'s'*16
        self.group_snapshot='r_'+'g'*16
        self.aliases=['s_'+'a'*16,'s_'+'b'*16]
        connection=sqlite3.connect(self.work/'data.sqlite3')
        connection.execute('ATTACH DATABASE ? AS identities',(str(self.work/'identity.sqlite3'),))
        connection.executescript((ROOT/'tests/fixtures/legacy_store_v1.sql').read_text(encoding='utf-8'))
        metadata=[('store_id','store_'+'z'*16),('generation','2'),('format_version','1')]
        for table in ('metadata','identities.metadata'):
            connection.executemany('INSERT INTO '+table+' VALUES (?,?)',metadata)
        assessment,population='a_'+'a'*16,'p_'+'p'*16
        connection.execute('INSERT INTO assessments VALUES (?,?,?,?)',(assessment,CONTEXT['source_namespace'],CONTEXT['assessment_ref'],CONTEXT['framework_ref']))
        connection.execute('INSERT INTO populations VALUES (?,?,?)',(population,CONTEXT['source_namespace'],CONTEXT['population_ref']))
        context_json=canonical_json(CONTEXT)
        for snapshot,source,method,ref in ((self.student_snapshot,self.student_source,STUDENT,'v_'+'s'*16),(self.group_snapshot,self.group_source,GROUP,'v_'+'g'*16)):
            payload=source.read_bytes(); checksum=digest(payload)
            (self.work/'originals'/(checksum+'.xlsx')).write_bytes(payload)
            connection.execute('INSERT INTO imports VALUES (?,?,?,?,?,?,?,?,?,?)',(snapshot,checksum,method,'1.1.0','0.1.0',digest(context_json.encode()),context_json,assessment,population,ref))
        for i,alias in enumerate(self.aliases):
            connection.execute('INSERT INTO identities.students VALUES (?,?,?,?)',(CONTEXT['source_namespace'],PRIVATE_MARKERS[2+i],alias,PRIVATE_MARKERS[i]))
            scores=[10.5,1444,0.625] if i==0 else [0,None,0]
            connection.execute('INSERT INTO attempt_summaries VALUES (?,?,?,?,?,?)',(self.student_snapshot,alias,*scores,'{}'))
            for field,cell in zip(('raw_score','scale_score','percent_ratio'),('H','I','J')):
                connection.execute('INSERT INTO source_cells VALUES (?,?,?,0,?)',(self.student_snapshot,alias,field,cell+str(i+4)))
            for n,value in enumerate(([0,0.625] if i==0 else [1,None]),1):
                code=f'7.{n}.A.i'; label=f'7.{n}(A.i) [R]'
                connection.execute('INSERT INTO student_standard_results VALUES (?,?,?,?,?,?)',(self.student_snapshot,alias,code,value,label,'R'))
                connection.execute('INSERT INTO source_cells VALUES (?,?,?,0,?)',(self.student_snapshot,alias,code,('F' if n==1 else 'G')+str(i+4)))
        for i,value in enumerate((0,0.625,None),1):
            connection.execute('INSERT INTO group_item_results VALUES (?,?,?,?,?)',(self.group_snapshot,str(i),f'7.{i}.A.i',2,value))
            connection.execute('INSERT INTO source_cells VALUES (?,?,?,0,?)',(self.group_snapshot,str(i),'reported_correct_ratio','E'+str(i+2)))
        connection.commit(); connection.close()

    def test_old_store_requires_explicit_migration(self):
        with self.assertRaisesRegex(PipelineError,'^store_migration_required$'):
            connect(self.work)

    def test_migration_preserves_aliases_values_provenance_and_reimport_identity(self):
        self.assertTrue(migrate_store(self.work))
        connection=connect(self.work)
        try:
            self.assertEqual(read_generation(connection),('store_'+'z'*16,3))
            self.assertEqual(connection.execute('SELECT count(*) FROM standards').fetchone()[0],3)
            self.assertEqual(connection.execute('SELECT count(*) FROM source_cells').fetchone()[0],13)
            self.assertEqual(connection.execute('SELECT parser_version FROM imports WHERE snapshot_key=?',(self.student_snapshot,)).fetchone()[0],'0.1.0')
            packet=build_packet(connection,self.student_snapshot)
            self.assertEqual(packet['tables']['students']['rows'],[[self.aliases[0],10.5,1444,0.625,0,0.625],[self.aliases[1],0,None,0,1,None]])
            group=build_packet(connection,self.group_snapshot)
            self.assertEqual(packet['standards_scope_key'],group['standards_scope_key'])
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:
            connection.close()
        backups=list((self.work/'migrations').glob('v1_*'))
        self.assertEqual(len(backups),1)
        for file in ('data.sqlite3','identity.sqlite3'):
            old=sqlite3.connect(backups[0]/file)
            self.assertEqual(old.execute("SELECT value FROM metadata WHERE key='format_version'").fetchone()[0],'1')
            old.close()
        self.assertFalse(migrate_store(self.work))
        self.assertEqual(import_report(self.work,self.student_source,STUDENT,CONTEXT),(self.student_snapshot,False))

    def test_unrecognized_legacy_standard_rolls_back_catalog_and_metadata(self):
        old=sqlite3.connect(self.work/'data.sqlite3')
        # Fail after student rows and earlier group rows have been backfilled.
        old.execute("UPDATE group_item_results SET standard_code='07.3.A.i' WHERE question_label='3'")
        old.commit(); old.close()
        with self.assertRaisesRegex(PipelineError,'^legacy_standard_requires_review$'):
            migrate_store(self.work)
        old=connect(self.work,allow_legacy=True)
        try:
            self.assertEqual(read_generation(old,allow_legacy=True),('store_'+'z'*16,2))
            self.assertEqual(old.execute("SELECT count(*) FROM sqlite_master WHERE name='standards'").fetchone()[0],0)
            self.assertEqual(old.execute('SELECT count(*) FROM student_standard_results').fetchone()[0],4)
            self.assertEqual(old.execute('SELECT count(*) FROM identities.students').fetchone()[0],2)
        finally:
            old.close()

    def test_empty_legacy_store_can_be_migrated_without_recreating_identity_map(self):
        empty=self.base/'empty-legacy'
        (empty/'originals').mkdir(parents=True)
        old=sqlite3.connect(empty/'data.sqlite3')
        old.execute('ATTACH DATABASE ? AS identities',(str(empty/'identity.sqlite3'),))
        old.executescript((ROOT/'tests/fixtures/legacy_store_v1.sql').read_text(encoding='utf-8'))
        metadata=[('store_id','store_'+'e'*16),('generation','0'),('format_version','1')]
        for table in ('metadata','identities.metadata'):
            old.executemany('INSERT INTO '+table+' VALUES (?,?)',metadata)
        old.commit(); old.close()
        self.assertTrue(migrate_store(empty))
        current=connect(empty)
        try:
            self.assertEqual(read_generation(current),('store_'+'e'*16,1))
            self.assertEqual(current.execute('SELECT count(*) FROM standards').fetchone()[0],0)
            self.assertEqual(current.execute('SELECT count(*) FROM identities.students').fetchone()[0],0)
        finally:
            current.close()

    def test_trusted_local_migration_command_emits_no_private_values(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        import process_reports
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.dict('os.environ',{'DATAGOBLIN_SYNC_DIR':str(self.base/'sync')}),redirect_stdout(stdout),redirect_stderr(stderr):
            self.assertEqual(process_reports.main(['--work-dir',str(self.work),'migrate-store']),0)
        public=stdout.getvalue()+stderr.getvalue()
        self.assertIn('migrated',public)
        for private in (*CONTEXT.values(),*PRIVATE_MARKERS,str(self.work)):
            self.assertNotIn(private,public)


if __name__=='__main__':
    unittest.main()

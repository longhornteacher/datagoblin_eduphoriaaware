"""Cross-subject/level tests are independent synthetic report shapes only."""

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from aware_results.errors import PipelineError
from aware_results.export import build_packet
from aware_results.migrate import migrate_store
from aware_results.standards import normalize_standard,standard_sort_key
from aware_results.storage import connect,import_report,initialize_store,read_generation,validate_context
from synthetic_xlsx import students,items
import test_standards as legacy_tests


STUDENT='student_learning_standards'
GROUP='group_item_analysis'


class CrossSubjectStandardsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve(); self.work=self.base/'work'
        initialize_store(self.work)

    def context(self,subject,course=None,version='synthetic-version'):
        reference='SYNTHETIC:'+subject+':'+version+(':'+course if course else '')
        result={'source_namespace':'SYNTHETIC_SOURCE','assessment_ref':reference+':assessment',
                'population_ref':'SYNTHETIC_ROSTER','framework_ref':reference,
                'subject':subject,'framework_version':version}
        if course: result['course_code']=course
        return result

    def ingest(self,spec,method,context):
        # Different synthetic source metadata distinguishes byte-identical
        # numeric report shapes used intentionally in separate subject scopes.
        spec.put('A1','SYNTHETIC_CONTEXT_'+context['framework_ref'])
        source=self.base/'synthetic.xlsx'; spec.save(source)
        return import_report(self.work,source,method,context)[0]

    def test_normalizer_accepts_kindergarten_numeric_and_explicit_course_forms(self):
        for source,code,grade,course in [
            ('K.2(B) [S]','K.2.B',None,None),('k.2.b','K.2.B',None,None),
            ('1.2A','1.2.A',1,None),('12.4(C)','12.4.C',12,None),
            ('A.5(C) [R]','A.5.C',None,'A'),('E1.2(A.i)','E1.2.A.i',None,'E1'),
            ('B.5.A','B.5.A',None,'B'),('ART1.3.B','ART1.3.B',None,'ART1'),
        ]:
            with self.subTest(source=source):
                standard=normalize_standard(source)
                self.assertEqual((standard.code,standard.grade,standard.course_code),(code,grade,course))
                self.assertEqual(standard.source_label,source)
        self.assertNotEqual(normalize_standard('0.2.A').code,normalize_standard('K.2.A').code)
        with self.assertRaisesRegex(PipelineError,'^standard_label_unrecognized$'):
            normalize_standard('111.39.C')

    def test_numeric_codes_remain_distinct_across_all_registered_subjects(self):
        subjects=['mathematics','science','social-studies','elar','slar','fine-arts','technology','health','physical-education','languages']
        scopes=[]
        for subject in subjects:
            spec=items(2); spec.put('D3','5.2.B'); spec.put('D4','5.3.A')
            snapshot=self.ingest(spec,GROUP,self.context(subject))
            connection=connect(self.work)
            scopes.append(build_packet(connection,snapshot)['standards_scope_key']); connection.close()
        self.assertEqual(len(set(scopes)),len(subjects))
        connection=connect(self.work)
        self.assertEqual(connection.execute("SELECT count(*) FROM standards WHERE standard_code='5.2.B'").fetchone()[0],len(subjects))
        connection.close()

    def test_kindergarten_and_every_numbered_grade_in_both_report_methods(self):
        context=self.context('mathematics')
        for level in ['K',*map(str,range(1,13))]:
            with self.subTest(level=level):
                spec=students(2); spec.put('F3',f'{level}.2(A)'); spec.put('G3',f'{level}.3(B)')
                first=self.ingest(spec,STUDENT,context)
                group=items(2); group.put('D3',f'{level}.2.A'); group.put('D4',f'{level}.3.B')
                second=self.ingest(group,GROUP,context)
                connection=connect(self.work)
                packet=build_packet(connection,first)
                self.assertEqual(packet['standards_scope_key'],build_packet(connection,second)['standards_scope_key'])
                standard=connection.execute('SELECT grade,level_code,level_kind FROM standards WHERE standard_code=?',(f'{level}.2.A',)).fetchone()
                self.assertEqual(tuple(standard),(None,'K','kindergarten') if level=='K' else (int(level),level,'grade'))
                tags=connection.execute('SELECT source_tag FROM standard_source_labels WHERE snapshot_key=?',(first,)).fetchall()
                self.assertTrue(all(row[0] is None for row in tags))
                connection.close()

    def test_high_school_courses_store_no_guessed_grade_and_share_cross_method_keys(self):
        for subject,course in [('mathematics','A'),('science','B'),('elar','E1'),('social-studies','US'),('fine-arts','ART1'),('technology','CS1')]:
            with self.subTest(subject=subject,course=course):
                context=self.context(subject,course)
                spec=students(2); spec.put('F3',f'{course}.2(A)'); spec.put('G3',f'{course}.3(B) [S]')
                first=self.ingest(spec,STUDENT,context)
                group=items(2); group.put('D3',f'{course}.2.A'); group.put('D4',f'{course}.3.B')
                second=self.ingest(group,GROUP,context)
                connection=connect(self.work)
                standard=connection.execute('SELECT grade,level_kind,course_code FROM standards WHERE standard_code=?',(f'{course}.2.A',)).fetchone()
                self.assertEqual(tuple(standard),(None,'course',course))
                self.assertEqual(build_packet(connection,first)['standards_scope_key'],build_packet(connection,second)['standards_scope_key'])
                self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
                connection.close()

    def test_course_prefix_needs_explicit_matching_subject_version_and_course(self):
        spec=items(2); spec.put('D3','A.2.A'); spec.put('D4','A.3.B')
        missing=self.context('mathematics')
        for context in [missing,self.context('mathematics','E1')]:
            with self.assertRaisesRegex(PipelineError,'^course_scope_required_or_conflicting$'):
                self.ingest(spec,GROUP,context)
        connection=connect(self.work)
        self.assertEqual(connection.execute('SELECT count(*) FROM imports').fetchone()[0],0)
        self.assertEqual(connection.execute('SELECT count(*) FROM standards').fetchone()[0],0)
        connection.close()
        with self.assertRaisesRegex(PipelineError,'^course_context_invalid$'):
            validate_context({k:v for k,v in self.context('mathematics','A').items() if k not in ('subject','framework_version')})

    def test_conflicting_subject_for_same_framework_is_rejected(self):
        context=self.context('mathematics')
        self.ingest(items(2),GROUP,context)
        changed=items(2); changed.put('E3',0.125,2)
        with self.assertRaisesRegex(PipelineError,'^framework_details_conflict$'):
            self.ingest(changed,GROUP,{**context,'assessment_ref':'SYNTHETIC_OTHER_TEST','subject':'science'})

    def test_numeric_framework_cannot_be_silently_reclassified_as_course(self):
        context=self.context('mathematics')
        self.ingest(items(2),GROUP,context)
        course=items(2); course.put('D3','A.2.A'); course.put('D4','A.3.B')
        with self.assertRaisesRegex(PipelineError,'^framework_course_conflict$'):
            self.ingest(course,GROUP,{**context,'assessment_ref':'SYNTHETIC_COURSE','course_code':'A'})

    def test_order_handles_kindergarten_grades_and_courses_without_type_errors(self):
        codes=['E1.2.A','A.5.C','12.2.A','2.2.A','K.2.B','K.1.A']
        self.assertEqual(sorted(codes,key=standard_sort_key),['K.1.A','K.2.B','2.2.A','12.2.A','A.5.C','E1.2.A'])


class FormatTwoMigrationTest(unittest.TestCase):
    def setUp(self):
        # Populate a frozen v2 schema with synthetic v1 fixture records, rather
        # than generating an old schema from the current implementation.
        legacy=legacy_tests.LegacyCatalogMigrationTest(methodName='test_old_store_requires_explicit_migration')
        legacy.setUp(); self.addCleanup(legacy.doCleanups)
        self.legacy=legacy
        self.work=legacy.base/'format-two'; (self.work/'originals').mkdir(parents=True)
        connection=sqlite3.connect(self.work/'data.sqlite3')
        connection.execute('ATTACH DATABASE ? AS identities',(str(self.work/'identity.sqlite3'),))
        connection.executescript((ROOT/'tests/fixtures/legacy_store_v2.sql').read_text())
        connection.execute('ATTACH DATABASE ? AS old_data',(str(legacy.work/'data.sqlite3'),))
        connection.execute('ATTACH DATABASE ? AS old_identity',(str(legacy.work/'identity.sqlite3'),))
        for table in ('metadata','assessments','populations','imports','attempt_summaries','source_cells'):
            connection.execute('INSERT INTO '+table+' SELECT * FROM old_data.'+table)
        for table in ('metadata','students'):
            connection.execute('INSERT INTO identities.'+table+' SELECT * FROM old_identity.'+table)
        for table in ('metadata','identities.metadata'):
            connection.execute("UPDATE "+table+" SET value='2' WHERE key='format_version'")
        self.framework='f_'+'f'*16
        connection.execute('INSERT INTO standards_frameworks VALUES (?,?,?)',(self.framework,'SYNTHETIC_SCOPE','SYNTHETIC_TEKS_SUBJECT_VERSION'))
        for n in range(1,4):
            code=f'7.{n}.A.i'; key='t_'+str(n)*16
            connection.execute('INSERT INTO standards VALUES (?,?,?,?,?,?,?,?)',(key,self.framework,code,7,n,'A','i','SYNTHETIC_RETAINED_DESCRIPTION' if n==1 else None))
        connection.execute("INSERT INTO student_standard_results SELECT r.*,s.standard_key FROM old_data.student_standard_results r JOIN standards s ON s.standard_code=r.standard_code")
        connection.execute("INSERT INTO group_item_results SELECT r.*,s.standard_key FROM old_data.group_item_results r JOIN standards s ON s.standard_code=r.standard_code")
        connection.execute("INSERT INTO standard_source_labels SELECT DISTINCT snapshot_key,'student_standard',r.standard_code,s.standard_key,source_label,source_tag FROM old_data.student_standard_results r JOIN standards s ON s.standard_code=r.standard_code")
        connection.execute("INSERT INTO standard_source_labels SELECT snapshot_key,'group_item',question_label,s.standard_key,r.standard_code,NULL FROM old_data.group_item_results r JOIN standards s ON s.standard_code=r.standard_code")
        connection.execute("UPDATE imports SET parser_version='0.2.0',contract_version='1.2.0'")
        connection.commit(); connection.close()
        for file in (legacy.work/'originals').iterdir(): shutil.copyfile(file,self.work/'originals'/file.name)

    def test_format_two_migration_preserves_scope_keys_values_aliases_and_descriptions(self):
        with self.assertRaisesRegex(PipelineError,'^store_migration_required$'): connect(self.work)
        self.assertTrue(migrate_store(self.work)); self.assertFalse(migrate_store(self.work))
        connection=connect(self.work)
        self.assertEqual(read_generation(connection),('store_'+'z'*16,3))
        packet=build_packet(connection,self.legacy.student_snapshot)
        self.assertEqual(packet['standards_scope_key'],self.framework)
        self.assertEqual([row[0] for row in packet['tables']['students']['rows']],self.legacy.aliases)
        self.assertEqual(connection.execute('SELECT description FROM standards WHERE standard_key=?',('t_'+'1'*16,)).fetchone()[0],'SYNTHETIC_RETAINED_DESCRIPTION')
        self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='format_version'").fetchone()[0],'3')
        connection.close()
        self.assertEqual(len(list((self.work/'migrations').glob('v2_*'))),1)
        self.assertEqual(import_report(self.work,self.legacy.student_source,STUDENT,legacy_tests.CONTEXT),(self.legacy.student_snapshot,False))

    def test_invalid_v2_code_rolls_back_new_columns_and_metadata(self):
        connection=sqlite3.connect(self.work/'data.sqlite3')
        connection.execute("UPDATE standards SET grade=99 WHERE standard_code='7.1.A.i'")
        connection.commit(); connection.close()
        with self.assertRaisesRegex(PipelineError,'^legacy_standard_requires_review$'): migrate_store(self.work)
        connection=connect(self.work,allow_legacy=True)
        self.assertEqual(connection.execute("SELECT value FROM metadata WHERE key='format_version'").fetchone()[0],'2')
        self.assertEqual([row[1] for row in connection.execute('PRAGMA table_info(standards_frameworks)')],['framework_key','source_namespace','framework_ref'])
        self.assertEqual(connection.execute('SELECT count(*) FROM standards').fetchone()[0],3)
        connection.close()


if __name__=='__main__': unittest.main()

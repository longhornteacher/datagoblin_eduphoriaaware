"""End-to-end tests use only independently constructed synthetic workbooks."""

from contextlib import redirect_stderr, redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from aware_results.adapters import parse_xlsx
from aware_results.errors import PipelineError
from aware_results.export import build_packet, export_packet, packet_bytes
from aware_results.publish import publish_store
from aware_results.storage import import_report, initialize_store, connect, read_generation, validate_work_root, writer_lock
import process_reports
import read_packet
from sync_folder import initialize_sync_folder
from synthetic_xlsx import PRIVATE_MARKERS, students, items


STUDENT = 'student_learning_standards'
ITEM = 'group_item_analysis'
CONTEXT = {'source_namespace':'SYNTHETIC_PRIVATE_NAMESPACE','assessment_ref':'SYNTHETIC_PRIVATE_ASSESSMENT','population_ref':'SYNTHETIC_PRIVATE_POPULATION','framework_ref':'SYNTHETIC_PRIVATE_FRAMEWORK'}


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.work = self.base / 'work'
        self.sync = self.base / 'sync'
        self.source = self.base / 'synthetic-private-source.xlsx'
        initialize_store(self.work)

    def ingest(self, spec=None, method=STUDENT, context=None):
        (spec or students()).save(self.source)
        return import_report(self.work, self.source, method, context or CONTEXT)

    def packet(self, snapshot):
        connection = connect(self.work)
        try:
            return build_packet(connection, snapshot)
        finally:
            connection.close()

    def state(self):
        connection = connect(self.work)
        try:
            return (read_generation(connection), connection.execute('SELECT count(*) FROM imports').fetchone()[0], connection.execute('SELECT count(*) FROM identities.students').fetchone()[0])
        finally:
            connection.close()

    def assert_rejected(self, spec, method=STUDENT, code=None):
        before = self.state()
        with self.assertRaisesRegex(PipelineError, '^'+code+'$' if code else '^[a-z_]+$'):
            self.ingest(spec, method)
        self.assertEqual(self.state(), before)

    def test_dynamic_standard_counts_and_reordering(self):
        for count in (2, 4, 29, 33):
            for optional, reorder in ((True,False),(False,True)):
                with self.subTest(count=count,optional=optional):
                    spec = students(count,optional=optional,reorder=reorder)
                    spec.save(self.source)
                    parsed = parse_xlsx(self.source.read_bytes(), STUDENT)
                    self.assertEqual(len(parsed.standards), count)
                    self.assertEqual(len(parsed.rows),2)
                    self.assertTrue(parsed.rows[0]['local_id'].startswith('000041'))
                    self.assertEqual(parsed.rows[0]['scores'],[10.5,1444,0.625])

    def test_dynamic_item_counts_and_column_order(self):
        for count in (3,5,41,45):
            with self.subTest(count=count):
                items(count,reorder=True).save(self.source)
                parsed = parse_xlsx(self.source.read_bytes(),ITEM)
                self.assertEqual(len(parsed.rows),count)
                self.assertEqual(parsed.rows[0]['ratio'],0)
                self.assertIsNone(parsed.rows[2]['ratio'])

    def test_lossless_zero_blank_partial_ratios_and_summary(self):
        snapshot,_ = self.ingest()
        packet = self.packet(snapshot)
        table = packet['tables']['students']
        by_raw = {row[1]:row for row in table['rows']}
        self.assertEqual(by_raw[10.5][3:], [0.625,0,0.625,None])
        self.assertEqual(by_raw[0][2:], [None,0,1,None,0.5])
        summary=packet['tables']['standard_summary']['rows']
        self.assertEqual(summary, [['7.1.A.i',0.5,2,0],['7.2.A.i',0.625,1,1],['7.3.A.i',0.5,1,1]])

    def test_repeat_import_no_duplicate_and_deterministic_export(self):
        snapshot,created = self.ingest()
        state=self.state()
        self.assertTrue(created)
        self.assertEqual(import_report(self.work,self.source,STUDENT,CONTEXT),(snapshot,False))
        self.assertEqual(self.state(),state)
        self.assertEqual(packet_bytes(self.packet(snapshot)),packet_bytes(self.packet(snapshot)))

    def test_corrupt_private_archive_is_not_silently_reused(self):
        self.ingest()
        archived=next((self.work/'originals').glob('*.xlsx'))
        archived.write_bytes(b'SYNTHETIC_CORRUPTED_ARCHIVE')
        with self.assertRaisesRegex(PipelineError,'^private_archive_conflict$'):
            import_report(self.work,self.source,STUDENT,CONTEXT)

    def test_changed_snapshot_preserves_aliases_and_old_values(self):
        first,_=self.ingest()
        old=self.packet(first)
        spec=students()
        spec.put('F4',0.75,1)
        second,_=self.ingest(spec)
        self.assertNotEqual(first,second)
        self.assertEqual(self.packet(first),old)
        self.assertEqual([row[0] for row in old['tables']['students']['rows']],[row[0] for row in self.packet(second)['tables']['students']['rows']])
        self.assertEqual(self.state()[1:],(2,2))

    def test_namespace_scopes_aliases(self):
        first,_=self.ingest()
        spec=students()
        spec.put('F4',0.75,1)
        second,_=self.ingest(spec,context={**CONTEXT,'source_namespace':'SYNTHETIC_SECOND_NAMESPACE'})
        self.assertFalse({row[0] for row in self.packet(first)['tables']['students']['rows']} & {row[0] for row in self.packet(second)['tables']['students']['rows']})

    def test_same_source_with_conflicting_context_stops(self):
        self.ingest()
        before=self.state()
        with self.assertRaisesRegex(PipelineError,'^source_context_conflict$'):
            import_report(self.work,self.source,STUDENT,{**CONTEXT,'population_ref':'DIFFERENT_PRIVATE_SCOPE'})
        self.assertEqual(self.state(),before)

    def test_late_identity_conflict_rolls_back_new_alias_and_results(self):
        self.ingest()
        spec=students()
        spec.put('B4','000099_SYNTHETIC_NEW_ID',3)
        spec.put('A5','SYNTHETIC_CONFLICTING_NAME',3)
        self.assert_rejected(spec,code='identity_context_conflict')

    def test_duplicate_ids_standards_and_questions_rejected(self):
        spec=students(); spec.put('B5',PRIVATE_MARKERS[2],3)
        self.assert_rejected(spec,code='duplicate_student')
        spec=students(); spec.put('G3','7.1(A.i) [S]')
        self.assert_rejected(spec,code='duplicate_standard')
        spec=items(); spec.put('C4',1)
        self.assert_rejected(spec,ITEM,'duplicate_or_invalid_question')

    def test_bad_metric_encodings_rejected_without_state_changes(self):
        for value,style in ((62.5,1),('62.5%',1),(True,1),({'formula':'1/2'},1),({'error':'#N/A'},1),(0.625,0),(0.625,2)):
            with self.subTest(value=value):
                spec=students(); spec.put('F4',value,style)
                self.assert_rejected(spec)

    def test_numeric_or_missing_id_rejected(self):
        for value in (41,None,'   '):
            spec=students(); spec.put('B4',value,3)
            self.assert_rejected(spec)

    def test_unknown_column_hidden_row_extra_sheet_and_bad_merge_rejected(self):
        spec=students(); spec.put('P2','SYNTHETIC_UNKNOWN_HEADER')
        self.assert_rejected(spec,code='unknown_header')
        spec=students(); spec.put('P4',0.5,1)
        self.assert_rejected(spec,code='unknown_populated_column')
        spec=students(); spec.hidden_rows.add(4)
        self.assert_rejected(spec,code='hidden_rows_unsupported')
        spec=students(); spec.extra_sheet=True
        self.assert_rejected(spec,code='single_worksheet_required')
        spec=students(); spec.auto_filter=True
        self.assert_rejected(spec,code='filtered_or_table_layout_unsupported')
        spec=students(); spec.merges.append('F4:F5')
        self.assert_rejected(spec,code='data_merge_unsupported')

    def test_item_population_and_group_bounds_rejected(self):
        spec=items(); spec.put('B4',3)
        self.assert_rejected(spec,ITEM,'varying_population_count')
        spec=items(); spec.put('B3',0)
        self.assert_rejected(spec,ITEM,'zero_population_with_result')
        spec=items(); spec.put('C8',99)
        self.assert_rejected(spec,ITEM,'data_outside_group')
        spec=items(); spec.merges.remove('A3:A7')
        self.assert_rejected(spec,ITEM,'single_group_merge_required')

    def test_item_export_excludes_population_count_and_never_creates_student_records(self):
        snapshot,_=self.ingest(items(),ITEM)
        packet=self.packet(snapshot)
        self.assertEqual(set(packet['tables']),{'group_items'})
        self.assertEqual(packet['tables']['group_items']['columns'],['question_label','standard_code','reported_correct_ratio'])
        self.assertEqual(packet['tables']['group_items']['rows'][0],['1','7.1.A.i',0])
        self.assertNotIn('total_students',packet_bytes(packet).decode())
        self.assertEqual(self.state()[2],0)

    def test_missing_identity_map_stops_instead_of_regenerating(self):
        self.ingest()
        (self.work/'identity.sqlite3').rename(self.work/'held-identity.sqlite3')
        with self.assertRaisesRegex(PipelineError,'^private_store_or_identity_missing$'):
            import_report(self.work,self.source,STUDENT,CONTEXT)
        self.assertFalse((self.work/'identity.sqlite3').exists())

    def test_generation_mismatch_and_writer_lock_stop(self):
        connection=sqlite3.connect(self.work/'identity.sqlite3')
        connection.execute("UPDATE metadata SET value='999' WHERE key='generation'")
        connection.commit(); connection.close()
        with self.assertRaisesRegex(PipelineError,'^identity_generation_mismatch$'):
            self.ingest()
        with writer_lock(self.work):
            with self.assertRaisesRegex(PipelineError,'^private_store_locked$'):
                self.ingest()

    def test_all_export_files_and_public_cli_output_exclude_markers(self):
        snapshot,_=self.ingest()
        output=self.base/'agent-packet'
        export_packet(self.work,snapshot,output,sync_root=self.sync)
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.dict('os.environ',{'DATAGOBLIN_SYNC_DIR':str(self.sync)}), redirect_stdout(stdout),redirect_stderr(stderr):
            rc=process_reports.main(['--work-dir',str(self.work),'import','--input',str(self.source),'--method',STUDENT,'--context',str(self.base/'MISSING_PRIVATE_CONTEXT_MARKER.json')])
        self.assertEqual(rc,1)
        public=''.join(p.read_text(encoding='utf-8') for p in output.iterdir())+stdout.getvalue()+stderr.getvalue()
        for marker in (*PRIVATE_MARKERS,*CONTEXT.values(),str(self.source),str(self.work),'MISSING_PRIVATE_CONTEXT_MARKER'):
            self.assertNotIn(marker,public)
        self.assertEqual(set(p.name for p in output.iterdir()),{'data.json','README.md'})

    def test_export_paths_and_existing_outputs_protected(self):
        snapshot,_=self.ingest()
        with self.assertRaisesRegex(PipelineError,'^export_private_directory_overlap$'):
            export_packet(self.work,snapshot,self.work/'leak')
        output=self.base/'packet'
        export_packet(self.work,snapshot,output)
        original=(output/'data.json').read_bytes()
        with self.assertRaisesRegex(PipelineError,'^export_destination_exists$'):
            export_packet(self.work,snapshot,output)
        self.assertEqual((output/'data.json').read_bytes(),original)

    def test_work_root_is_absolute_and_disjoint(self):
        for path in (ROOT/'private',ROOT.parent,self.sync/'active'):
            with self.assertRaises(PipelineError):
                validate_work_root(path,project_root=ROOT,sync_root=self.sync)

    def test_publish_closed_matched_snapshots_and_idempotent_manifest(self):
        self.ingest()
        initialize_sync_folder(self.sync)
        publish_store(self.work,self.sync)
        manifests=list((self.sync/'manifests').glob('*.json'))
        self.assertEqual(len(manifests),1)
        before=manifests[0].read_bytes()
        manifest=json.loads(before)
        self.assertEqual(manifest['generation'],1)
        self.assertEqual(len(list((self.sync/'originals').glob('*.xlsx'))),1)
        self.assertEqual(len(list(self.sync.rglob('*-wal'))),0)
        self.assertTrue((self.sync/'identity'/manifest['identity']['file']).is_file())
        generations=[]
        for folder,key in (('normalized','normalized'),('identity','identity')):
            copy=self.sync/folder/manifest[key]['file']
            self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(),manifest[key]['sha256'])
            connection=sqlite3.connect(copy)
            generations.append(dict(connection.execute('SELECT key,value FROM metadata')))
            table='attempt_summaries' if folder=='normalized' else 'students'
            self.assertEqual(connection.execute('SELECT count(*) FROM '+table).fetchone()[0],2)
            connection.close()
        self.assertEqual(generations[0],generations[1])
        publish_store(self.work,self.sync)
        self.assertEqual(manifests[0].read_bytes(),before)

    def test_incomplete_or_conflicting_sync_copy_never_gets_committed_manifest(self):
        self.ingest()
        initialize_sync_folder(self.sync)
        publish_store(self.work,self.sync)
        manifest=next((self.sync/'manifests').glob('*.json'))
        record=json.loads(manifest.read_text())
        manifest.unlink()
        (self.sync/'identity'/record['identity']['file']).write_bytes(b'SYNTHETIC_INTERRUPTED_COPY')
        with self.assertRaisesRegex(PipelineError,'^sync_snapshot_conflict$'):
            publish_store(self.work,self.sync)
        self.assertEqual(list((self.sync/'manifests').glob('*.json')),[])

    def test_cli_argument_errors_do_not_echo_private_values(self):
        stdout,stderr=io.StringIO(),io.StringIO()
        with redirect_stdout(stdout),redirect_stderr(stderr):
            rc=process_reports.main(['--SYNTHETIC_PRIVATE_UNKNOWN_ARGUMENT'])
        self.assertEqual(rc,1)
        self.assertNotIn('SYNTHETIC_PRIVATE_UNKNOWN_ARGUMENT',stdout.getvalue()+stderr.getvalue())

    def test_packet_reader_limits_and_projects_data(self):
        snapshot,_=self.ingest()
        packet=self.packet(snapshot)
        description=read_packet.select(packet)
        self.assertNotIn('rows',description['tables']['students'])
        first=read_packet.select(packet,table='students',standard='7.1.A.i',limit=1)
        self.assertEqual(first['standards_scope_key'],packet['standards_scope_key'])
        self.assertEqual(first['columns'],['student_alias','std:7.1.A.i'])
        self.assertEqual(len(first['rows']),1)
        self.assertEqual(first['next_offset'],1)
        second=read_packet.select(packet,table='students',standard='7.1.A.i',offset=1,limit=1)
        self.assertIsNone(second['next_offset'])
        self.assertNotEqual(first['rows'][0][0],second['rows'][0][0])
        specific=read_packet.select(packet,table='students',student=first['rows'][0][0])
        self.assertEqual(specific['matching_rows'],1)
        summary=read_packet.select(packet,table='standard_summary',standard='7.1.A.i')
        self.assertEqual(summary['rows'],[['7.1.A.i',0.5,2,0]])
        with self.assertRaises(read_packet.PacketError):
            read_packet.select(packet,table='students',limit=1001)

    def test_all_missing_standard_has_null_mean_and_explicit_missing_count(self):
        spec=students(); spec.put('F4',None,1); spec.put('F5',None,1)
        snapshot,_=self.ingest(spec)
        self.assertEqual(self.packet(snapshot)['tables']['standard_summary']['rows'][0],['7.1.A.i',None,0,2])

    def test_missing_metric_rows_retain_full_standard_grid_and_provenance(self):
        snapshot,_=self.ingest()
        connection=connect(self.work)
        try:
            self.assertEqual(connection.execute('SELECT count(*) FROM student_standard_results').fetchone()[0],6)
            self.assertEqual(connection.execute('SELECT count(*) FROM source_cells').fetchone()[0],12)
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:
            connection.close()

    def test_matrix_reduces_repeated_keys_without_losing_values(self):
        snapshot,_=self.ingest(students(29))
        table=self.packet(snapshot)['tables']['students']
        objects=[dict(zip(table['columns'],row)) for row in table['rows']]
        matrix_bytes=len(json.dumps(table,separators=(',',':')).encode())
        object_bytes=len(json.dumps(objects,separators=(',',':')).encode())
        self.assertLess(matrix_bytes,object_bytes)

    def test_complete_cli_workflow_with_synthetic_inputs(self):
        cli_work=self.base/'cli-work'
        context_path=self.base/'SYNTHETIC_PRIVATE_CONTEXT.json'
        context_path.write_text(json.dumps(CONTEXT),encoding='utf-8')
        students(29).save(self.source)
        initialize_sync_folder(self.sync)
        public=[]
        def command(arguments):
            stdout,stderr=io.StringIO(),io.StringIO()
            with redirect_stdout(stdout),redirect_stderr(stderr):
                code=process_reports.main(arguments)
            self.assertEqual(code,0,stderr.getvalue())
            public.extend([stdout.getvalue(),stderr.getvalue()])
            return stdout.getvalue()
        with patch.dict('os.environ',{'DATAGOBLIN_WORK_DIR':str(cli_work),'DATAGOBLIN_SYNC_DIR':str(self.sync)}):
            command(['init-store'])
            result=json.loads(command(['import','--input',str(self.source),'--method',STUDENT,'--context',str(context_path)]))
            self.assertEqual(result['status'],'imported')
            repeated=json.loads(command(['import','--input',str(self.source),'--method',STUDENT,'--context',str(context_path)]))
            self.assertEqual(repeated,{'status':'already_imported','snapshot_key':result['snapshot_key']})
            output=self.base/'cli-output'
            command(['export','--snapshot',result['snapshot_key'],'--out',str(output)])
            command(['publish'])
            stdout=io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(read_packet.main(['--packet',str(output),'--table','standard_summary','--limit','2']),0)
            summary=json.loads(stdout.getvalue())
            self.assertEqual(len(summary['rows']),2)
            self.assertEqual(summary['matching_rows'],29)
            public.append(stdout.getvalue())
        for marker in (*PRIVATE_MARKERS,*CONTEXT.values(),str(cli_work),str(self.sync),str(self.source)):
            self.assertNotIn(marker,''.join(public))


if __name__ == '__main__':
    unittest.main()

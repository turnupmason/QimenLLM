import sqlite3
from qimenllm.cases.repository import CaseRepository
from qimenllm.knowledge.db import connect
from support import DatabaseTest


class CaseTests(DatabaseTest):
    def setUp(self):
        super().setUp()
        self.source=self.seed_event()
        self.repo=CaseRepository(self.db)
        for chart,event in (('chart-a','event'),('chart-b','event'),('chart-other','event-other')):
            self.repo.put_chart(chart_id=chart,event_id=event,source_id=self.source['source_id'],payload={'original_diagram':'engineering fixture'})
        with connect(self.db) as conn:
            for record,seq,kind,phase in (
                ('question',0,'dialogue','pre_prediction'),('prediction',1,'prediction','prediction'),
                ('feedback',2,'feedback','post_feedback'),('continuation',3,'continuation','post_feedback')):
                conn.execute('''INSERT INTO case_records VALUES (?, 'event','chart-a',?,?,?,?,'author',?,'{}','author_explicit',NULL)''',
                             (record,seq,kind,phase,self.source['source_id'],record))
            conn.execute("INSERT INTO dataset_releases VALUES ('release',?,0,?)",(self.source['data_version'],'0'*64))
            conn.execute("INSERT INTO split_assignments VALUES ('release','family','train')")
            conn.execute("INSERT INTO split_assignments VALUES ('release','family-other','test')")
            conn.execute("""INSERT INTO training_tasks VALUES ('task','release','family','train','event','engineering',1,
                'prediction','candidate',?,?)""",(self.source['data_version'],'0'*64))

    def test_multi_event_multi_chart_without_fixed_chart_count(self):
        with connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM case_events WHERE case_id=\'case\'').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM charts WHERE event_id=\'event\'').fetchone()[0],2)
        self.assertEqual(self.repo.get_chart('chart-b')['validation_status'],'original_unparsed')
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError): conn.execute("UPDATE charts SET chart_json='{}'")

    def test_record_cannot_point_to_another_events_chart(self):
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""INSERT INTO case_records VALUES ('bad','event','chart-other',9,'dialogue','unknown',?,NULL,'x','{}','not_explicit',NULL)""",
                             (self.source['source_id'],))

    def test_evidence_cannot_point_to_another_events_chart(self):
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO evidence_links VALUES ('prediction',?,NULL,'chart-other','x','fixture')",(self.source['source_id'],))

    def test_one_family_one_split_and_tasks_cannot_override_split(self):
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError): conn.execute("INSERT INTO split_assignments VALUES ('release','family','test')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""INSERT INTO training_tasks VALUES ('bad','release','family','test','event','x',1,
                    'prediction','candidate',?,?)""",(self.source['data_version'],'0'*64))

    def test_wrong_family_is_blocked_even_with_existing_split(self):
        with connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("""INSERT INTO training_tasks VALUES ('bad','release','family-other','test','event','x',1,
                    'prediction','candidate',?,?)""",(self.source['data_version'],'0'*64))

    def test_prediction_feedback_future_and_target_never_enter_inputs(self):
        with connect(self.db) as conn:
            conn.execute("INSERT INTO task_inputs VALUES ('task','question')")
            for record in ('prediction','feedback','continuation'):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute('INSERT INTO task_inputs VALUES (?,?)',('task',record))
        projected=self.repo.project_task('task')
        self.assertEqual([r['record_id'] for r in projected['input_records']],['question'])
        self.assertEqual(projected['target']['record_id'],'prediction')
        self.assertNotIn('background_json',projected)

    def test_event_family_and_records_cannot_change_after_grouping(self):
        with connect(self.db) as conn:
            for sql in ("UPDATE events SET family_id='family-other' WHERE event_id='event'",
                        "UPDATE case_records SET knowledge_phase='pre_prediction' WHERE record_id='feedback'"):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(sql)

    def test_frozen_release_cannot_be_reassigned_or_unfrozen(self):
        with connect(self.db) as conn:
            conn.execute("UPDATE dataset_releases SET frozen=1 WHERE release_id='release'")
            for sql in ("UPDATE split_assignments SET split='test' WHERE family_id='family'",
                        "DELETE FROM split_assignments", "UPDATE dataset_releases SET frozen=0",
                        "DELETE FROM dataset_releases", "INSERT INTO task_inputs VALUES ('task','question')"):
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(sql)

    def test_unknown_chronology_blocks_projection(self):
        with connect(self.db) as conn:
            conn.execute("INSERT INTO events VALUES ('unknown-event','family','{}','unknown')")
            conn.execute("""INSERT INTO case_records VALUES ('unknown-target','unknown-event',NULL,0,
                'prediction','unknown',?,NULL,'fixture','{}','author_explicit',NULL)""",(self.source['source_id'],))
            conn.execute("""INSERT INTO training_tasks VALUES ('unknown-task','release','family','train',
                'unknown-event','fixture',0,'unknown-target','candidate',?,?)""",(self.source['data_version'],'0'*64))
        with self.assertRaises(ValueError): self.repo.project_task('unknown-task')

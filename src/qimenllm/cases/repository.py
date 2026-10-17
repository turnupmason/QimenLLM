"""Historical chart storage and conservative, chronological task projection."""
from __future__ import annotations
import json
from pathlib import Path
from ..knowledge.db import connect, digest
from ..knowledge.importer import canonical


class CaseRepository:
    def __init__(self, db: str | Path):
        self.db = db

    def put_chart(self, *, chart_id: str, event_id: str, source_id: str,
                  payload: dict, casting_method: str | None = None,
                  method_version: str | None = None) -> None:
        body = canonical(payload)
        with connect(self.db) as conn:
            conn.execute('''INSERT INTO charts(chart_id,event_id,source_id,source_or_engine,
                casting_method,method_version,chart_json,content_sha256,validation_status)
                VALUES (?,?,?,'original',?,?,?,?,'original_unparsed')''',
                (chart_id,event_id,source_id,casting_method,method_version,body,digest(body.encode())))

    def get_chart(self, chart_id: str) -> dict:
        with connect(self.db) as conn:
            row = conn.execute('SELECT * FROM charts WHERE chart_id=?', (chart_id,)).fetchone()
            if row is None: raise KeyError(chart_id)
            result = dict(row)
            result['chart'] = json.loads(result.pop('chart_json'))
            return result

    def project_task(self, task_id: str) -> dict:
        """Inputs and target are returned separately; unknown chronology cannot be exported."""
        with connect(self.db) as conn:
            task = conn.execute('SELECT * FROM training_tasks WHERE task_id=?', (task_id,)).fetchone()
            if task is None: raise KeyError(task_id)
            event = conn.execute('SELECT * FROM events WHERE event_id=?', (task['event_id'],)).fetchone()
            if event['chronology_status'] != 'verified':
                raise ValueError('Chronology unverified; training export blocked')
            inputs = [dict(row) for row in conn.execute('''SELECT r.* FROM task_inputs i JOIN case_records r USING(record_id)
                WHERE i.task_id=? ORDER BY r.sequence''', (task_id,))]
            target = dict(conn.execute('SELECT * FROM case_records WHERE record_id=?', (task['target_record'],)).fetchone())
            # No unrestricted background_json or complete narrative enters predictive inputs.
            return {'task_id':task_id, 'split':task['split'], 'family_id':task['family_id'],
                    'input_records':inputs, 'target':target, 'validation_status':task['validation_status']}

-- Schema v1. All text/bytes are user-supplied; no seeded domain knowledge.
CREATE TABLE data_versions (
    version_id TEXT PRIMARY KEY NOT NULL,
    parent_id TEXT REFERENCES data_versions(version_id),
    operation TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
    created_at TEXT NOT NULL
);
CREATE TABLE books (
    book_id TEXT PRIMARY KEY NOT NULL,
    book_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author TEXT,
    edition TEXT,
    rights_status TEXT NOT NULL DEFAULT 'unreviewed'
        CHECK(rights_status IN ('unreviewed','research_authorized','public_authorized','restricted'))
);
CREATE TABLE chapters (
    chapter_id TEXT PRIMARY KEY NOT NULL,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    chapter_key TEXT NOT NULL,
    title TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence>=0),
    UNIQUE(book_id, chapter_key)
);
CREATE TABLE raw_documents (
    document_id TEXT PRIMARY KEY NOT NULL,
    sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256)=64),
    content BLOB NOT NULL CHECK(typeof(content)='blob'),
    byte_length INTEGER NOT NULL CHECK(byte_length=length(content)),
    media_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE chapter_revisions (
    revision_id TEXT PRIMARY KEY NOT NULL,
    chapter_id TEXT NOT NULL REFERENCES chapters(chapter_id),
    revision INTEGER NOT NULL CHECK(revision>0),
    document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
    data_version TEXT NOT NULL REFERENCES data_versions(version_id),
    input_origin TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(chapter_id, revision),
    UNIQUE(chapter_id, document_id)
);
CREATE TABLE source_reviews (
    review_id TEXT PRIMARY KEY NOT NULL,
    revision_id TEXT NOT NULL REFERENCES chapter_revisions(revision_id),
    status TEXT NOT NULL CHECK(status IN ('pending','confirmed','disputed')),
    reviewer TEXT NOT NULL,
    note TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);
CREATE TABLE source_spans (
    source_id TEXT PRIMARY KEY NOT NULL,
    revision_id TEXT NOT NULL REFERENCES chapter_revisions(revision_id),
    byte_start INTEGER NOT NULL CHECK(byte_start>=0),
    byte_end INTEGER NOT NULL CHECK(byte_end>byte_start),
    locator TEXT NOT NULL,
    UNIQUE(revision_id, byte_start, byte_end, locator)
);
CREATE TRIGGER source_span_bounds BEFORE INSERT ON source_spans BEGIN
    SELECT CASE WHEN NEW.byte_end > (
        SELECT d.byte_length FROM chapter_revisions r JOIN raw_documents d USING(document_id)
        WHERE r.revision_id=NEW.revision_id
    ) THEN RAISE(ABORT,'source span out of bounds') END;
END;
CREATE VIRTUAL TABLE chapter_search USING fts5(revision_id UNINDEXED, body, tokenize='unicode61');
CREATE TABLE methods (
    method_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    conventions_json TEXT NOT NULL CHECK(json_valid(conventions_json)),
    UNIQUE(name, version)
);
CREATE TABLE concepts (
    concept_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    definition TEXT NOT NULL
);
CREATE TABLE concept_links (
    left_id TEXT NOT NULL REFERENCES concepts(concept_id),
    right_id TEXT NOT NULL REFERENCES concepts(concept_id),
    relation TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    PRIMARY KEY(left_id, right_id, relation)
);
CREATE TABLE knowledge_items (
    item_id TEXT PRIMARY KEY NOT NULL,
    category TEXT NOT NULL CHECK(category IN
        ('foundation','casting','analogy','role','analysis','timing','commentary')),
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    method_id TEXT REFERENCES methods(method_id),
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    structured INTEGER NOT NULL DEFAULT 0 CHECK(structured IN (0,1)),
    applicability_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(applicability_confirmed IN (0,1)),
    compiled INTEGER NOT NULL DEFAULT 0 CHECK(compiled IN (0,1)),
    reference_only INTEGER NOT NULL DEFAULT 1 CHECK(reference_only IN (0,1)),
    disputed INTEGER NOT NULL DEFAULT 0 CHECK(disputed IN (0,1)),
    training_allowed INTEGER NOT NULL DEFAULT 0 CHECK(training_allowed IN (0,1)),
    evaluation_only INTEGER NOT NULL DEFAULT 0 CHECK(evaluation_only IN (0,1)),
    data_version TEXT NOT NULL REFERENCES data_versions(version_id),
    CHECK(NOT (training_allowed=1 AND evaluation_only=1))
);
CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY NOT NULL,
    item_id TEXT NOT NULL UNIQUE REFERENCES knowledge_items(item_id),
    method_id TEXT NOT NULL REFERENCES methods(method_id),
    domain TEXT NOT NULL,
    subtype TEXT,
    binding_json TEXT NOT NULL CHECK(json_valid(binding_json) AND json_type(binding_json)='object'),
    revision INTEGER NOT NULL CHECK(revision>0)
);
CREATE TABLE rule_conditions (
    condition_id TEXT PRIMARY KEY NOT NULL,
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    field TEXT NOT NULL CHECK(length(field)>0),
    operator TEXT NOT NULL CHECK(operator IN ('eq','ne','in','present')),
    expected_json TEXT NOT NULL CHECK(json_valid(expected_json)),
    kind TEXT NOT NULL CHECK(kind IN ('require','exclude')),
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    CHECK(operator<>'in' OR json_type(expected_json)='array')
);
CREATE TABLE rule_disagreements (
    disagreement_id TEXT PRIMARY KEY NOT NULL,
    rule_a TEXT NOT NULL REFERENCES rules(rule_id),
    rule_b TEXT NOT NULL REFERENCES rules(rule_id),
    explanation TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1)),
    CHECK(rule_a<>rule_b)
);
CREATE TABLE event_families (
    family_id TEXT PRIMARY KEY NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE cases (
    case_id TEXT PRIMARY KEY NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    title TEXT NOT NULL,
    completeness TEXT NOT NULL CHECK(completeness IN ('partial','complete','confirmed_complete')),
    data_version TEXT NOT NULL REFERENCES data_versions(version_id)
);
CREATE TABLE events (
    event_id TEXT PRIMARY KEY NOT NULL,
    family_id TEXT NOT NULL REFERENCES event_families(family_id),
    background_json TEXT NOT NULL CHECK(json_valid(background_json)),
    chronology_status TEXT NOT NULL CHECK(chronology_status IN ('unknown','ordered','verified'))
);
CREATE TABLE case_events (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    event_id TEXT NOT NULL REFERENCES events(event_id),
    sequence INTEGER NOT NULL CHECK(sequence>=0),
    PRIMARY KEY(case_id,event_id),
    UNIQUE(case_id, sequence)
);
CREATE TABLE charts (
    chart_id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    source_id TEXT REFERENCES source_spans(source_id),
    source_or_engine TEXT NOT NULL CHECK(source_or_engine IN ('original','engine')),
    casting_method TEXT,
    method_version TEXT,
    input_datetime TEXT,
    timezone TEXT,
    location_json TEXT CHECK(location_json IS NULL OR json_valid(location_json)),
    chart_json TEXT NOT NULL CHECK(json_valid(chart_json)),
    content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
    validation_status TEXT NOT NULL CHECK(validation_status IN
        ('original_unparsed','original_parsed','engine_unverified','engine_verified','mismatch')),
    UNIQUE(chart_id,event_id),
    CHECK(source_or_engine<>'original' OR source_id IS NOT NULL)
);
CREATE TABLE case_records (
    record_id TEXT PRIMARY KEY NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    chart_id TEXT,
    sequence INTEGER NOT NULL CHECK(sequence>=0),
    kind TEXT NOT NULL CHECK(kind IN
        ('dialogue','author_reasoning','role_selection','prediction','timing','feedback','continuation','outcome')),
    knowledge_phase TEXT NOT NULL CHECK(knowledge_phase IN ('pre_prediction','prediction','post_feedback','unknown')),
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    speaker TEXT,
    text TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    explicitness TEXT NOT NULL CHECK(explicitness IN ('author_explicit','not_explicit','agent_hypothesis')),
    reported_at TEXT,
    UNIQUE(event_id, sequence),
    UNIQUE(record_id,event_id),
    FOREIGN KEY(chart_id,event_id) REFERENCES charts(chart_id,event_id)
);
CREATE TABLE evidence_links (
    record_id TEXT NOT NULL REFERENCES case_records(record_id),
    source_id TEXT NOT NULL REFERENCES source_spans(source_id),
    rule_id TEXT REFERENCES rules(rule_id),
    chart_id TEXT REFERENCES charts(chart_id),
    fact_path TEXT,
    relation TEXT NOT NULL,
    PRIMARY KEY(record_id,source_id,relation)
);
CREATE TRIGGER evidence_same_event BEFORE INSERT ON evidence_links
WHEN NEW.chart_id IS NOT NULL BEGIN
    SELECT CASE WHEN (SELECT event_id FROM charts WHERE chart_id=NEW.chart_id)<>
        (SELECT event_id FROM case_records WHERE record_id=NEW.record_id)
        THEN RAISE(ABORT,'evidence chart event mismatch') END;
END;
CREATE TABLE dataset_releases (
    release_id TEXT PRIMARY KEY NOT NULL,
    data_version TEXT NOT NULL REFERENCES data_versions(version_id),
    frozen INTEGER NOT NULL CHECK(frozen IN (0,1)),
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64)
);
CREATE TABLE split_assignments (
    release_id TEXT NOT NULL REFERENCES dataset_releases(release_id),
    family_id TEXT NOT NULL REFERENCES event_families(family_id),
    split TEXT NOT NULL CHECK(split IN ('train','validation','test','unseen')),
    PRIMARY KEY(release_id,family_id),
    UNIQUE(release_id,family_id,split)
);
CREATE TABLE training_tasks (
    task_id TEXT PRIMARY KEY NOT NULL,
    release_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    split TEXT NOT NULL,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    task_type TEXT NOT NULL,
    cutoff_sequence INTEGER NOT NULL CHECK(cutoff_sequence>=0),
    target_record TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK(validation_status IN ('candidate','verified','rejected')),
    data_version TEXT NOT NULL REFERENCES data_versions(version_id),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    FOREIGN KEY(release_id,family_id,split) REFERENCES split_assignments(release_id,family_id,split),
    FOREIGN KEY(target_record,event_id) REFERENCES case_records(record_id,event_id)
);
CREATE TRIGGER task_family BEFORE INSERT ON training_tasks BEGIN
    SELECT CASE WHEN NEW.family_id<>(SELECT family_id FROM events WHERE event_id=NEW.event_id)
        THEN RAISE(ABORT,'event family mismatch') END;
    SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM case_records WHERE record_id=NEW.target_record
        AND event_id=NEW.event_id AND sequence=NEW.cutoff_sequence AND explicitness='author_explicit')
        THEN RAISE(ABORT,'target chronology or authorship invalid') END;
END;
CREATE TABLE task_inputs (
    task_id TEXT NOT NULL REFERENCES training_tasks(task_id),
    record_id TEXT NOT NULL REFERENCES case_records(record_id),
    PRIMARY KEY(task_id,record_id)
);
CREATE TRIGGER task_input_chronology BEFORE INSERT ON task_inputs BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM training_tasks t JOIN case_records r ON r.record_id=NEW.record_id
        WHERE t.task_id=NEW.task_id AND r.event_id=t.event_id
        AND r.sequence<t.cutoff_sequence AND r.record_id<>t.target_record
        AND r.knowledge_phase='pre_prediction'
        AND r.kind='dialogue' AND r.explicitness='author_explicit'
    ) THEN RAISE(ABORT,'future/feedback/target or unaudited input forbidden') END;
END;
CREATE TRIGGER frozen_split_insert BEFORE INSERT ON split_assignments
WHEN (SELECT frozen FROM dataset_releases WHERE release_id=NEW.release_id)=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;
CREATE TRIGGER frozen_split_update BEFORE UPDATE ON split_assignments
WHEN (SELECT frozen FROM dataset_releases WHERE release_id=OLD.release_id)=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;
CREATE TRIGGER frozen_split_delete BEFORE DELETE ON split_assignments
WHEN (SELECT frozen FROM dataset_releases WHERE release_id=OLD.release_id)=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;
CREATE TRIGGER release_freeze_update BEFORE UPDATE ON dataset_releases
WHEN OLD.frozen=1 OR NEW.release_id<>OLD.release_id OR NEW.data_version<>OLD.data_version
    OR NEW.manifest_sha256<>OLD.manifest_sha256
BEGIN SELECT RAISE(ABORT,'only initial release freeze allowed'); END;
CREATE TRIGGER release_freeze_delete BEFORE DELETE ON dataset_releases WHEN OLD.frozen=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;
CREATE TRIGGER frozen_task_insert BEFORE INSERT ON training_tasks
WHEN (SELECT frozen FROM dataset_releases WHERE release_id=NEW.release_id)=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;
CREATE TRIGGER frozen_input_insert BEFORE INSERT ON task_inputs
WHEN (SELECT d.frozen FROM dataset_releases d JOIN training_tasks t USING(release_id)
    WHERE t.task_id=NEW.task_id)=1
BEGIN SELECT RAISE(ABORT,'release frozen'); END;

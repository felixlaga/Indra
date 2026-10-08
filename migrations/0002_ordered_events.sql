-- A per-session counter is transactional. Unlike bigserial, a later cursor
-- cannot commit before an earlier event in the same stream.
CREATE TABLE session_event_counters (
    session_id uuid PRIMARY KEY REFERENCES research_sessions(id) ON DELETE CASCADE,
    sequence bigint NOT NULL DEFAULT 0,
    revision bigint NOT NULL DEFAULT 0
);
ALTER TABLE events ADD COLUMN sequence bigint;
WITH numbered AS (
    SELECT id, row_number() OVER (PARTITION BY session_id ORDER BY created_at, id) AS n
    FROM events
)
UPDATE events SET sequence = numbered.n FROM numbered WHERE events.id = numbered.id;
ALTER TABLE events ALTER COLUMN sequence SET NOT NULL;
CREATE UNIQUE INDEX events_session_sequence ON events(session_id, sequence);
INSERT INTO session_event_counters(session_id, sequence, revision)
SELECT session_id, max(sequence), max(sequence) FROM events GROUP BY session_id;

CREATE FUNCTION indra_order_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE next_sequence bigint;
BEGIN
    INSERT INTO session_event_counters(session_id) VALUES (NEW.session_id)
    ON CONFLICT DO NOTHING;
    UPDATE session_event_counters SET sequence = sequence + 1,
        revision = CASE WHEN NEW.event_type = 'research_progress' THEN revision ELSE sequence + 1 END
    WHERE session_id = NEW.session_id RETURNING sequence INTO next_sequence;
    NEW.sequence := next_sequence;
    PERFORM pg_notify('indra_events', NEW.session_id::text);
    RETURN NEW;
END;
$$;
CREATE TRIGGER events_order BEFORE INSERT ON events
FOR EACH ROW EXECUTE FUNCTION indra_order_event();

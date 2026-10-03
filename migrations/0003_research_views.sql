CREATE TABLE session_research_views (
    session_id uuid PRIMARY KEY REFERENCES research_sessions(id) ON DELETE CASCADE,
    requested_revision bigint NOT NULL,
    source_revision bigint,
    status text NOT NULL CHECK(status IN ('queued','running','ready','failed')),
    lease_token uuid,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    result jsonb NOT NULL DEFAULT '{}',
    error text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX research_views_queue ON session_research_views(status, updated_at);
CREATE INDEX events_claim_checks ON events(session_id, (payload->>'claim_id'))
WHERE event_type = 'claim_validated';

-- Materialization activity changes the event cursor, but not its own inputs.
CREATE OR REPLACE FUNCTION indra_order_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE next_sequence bigint;
BEGIN
    INSERT INTO session_event_counters(session_id) VALUES (NEW.session_id)
    ON CONFLICT DO NOTHING;
    UPDATE session_event_counters SET sequence = sequence + 1,
        revision = CASE WHEN NEW.event_type = 'research_progress'
            OR NEW.event_type LIKE 'derived_view_%' THEN revision ELSE sequence + 1 END
    WHERE session_id = NEW.session_id RETURNING sequence INTO next_sequence;
    NEW.sequence := next_sequence;
    PERFORM pg_notify('indra_events', NEW.session_id::text);
    RETURN NEW;
END;
$$;

-- Papers are global: refreshing metadata in one session also invalidates every
-- other session containing that paper, within the same transaction.
CREATE FUNCTION indra_paper_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE linked_session uuid;
BEGIN
    IF ROW(NEW.title,NEW.abstract,NEW.metadata,NEW.year,NEW.venue,NEW.citation_count,NEW.open_access_pdf_url)
       IS DISTINCT FROM ROW(OLD.title,OLD.abstract,OLD.metadata,OLD.year,OLD.venue,OLD.citation_count,OLD.open_access_pdf_url) THEN
        FOR linked_session IN SELECT DISTINCT session_id FROM session_papers
            WHERE paper_id=NEW.id ORDER BY session_id LOOP
            INSERT INTO events(id,session_id,paper_id,event_type,severity,payload)
            VALUES (gen_random_uuid(),linked_session,NEW.id,'paper_metadata_updated','info','{}');
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER papers_invalidate_views AFTER UPDATE ON papers
FOR EACH ROW EXECUTE FUNCTION indra_paper_changed();
CREATE INDEX IF NOT EXISTS session_papers_paper_lookup ON session_papers(paper_id);

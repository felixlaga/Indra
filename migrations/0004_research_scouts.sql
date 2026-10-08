-- Scout branches and a final per-session synthesis run as durable jobs.
ALTER TABLE jobs DROP CONSTRAINT jobs_job_type_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_job_type_check CHECK (
    job_type IN (
        'research_session',
        'branch_continue',
        'session_synthesis',
        'claim_extraction',
        'claim_validation',
        'export'
    )
);
-- At most one synthesis job per session, so concurrent branch completions
-- cannot enqueue it twice.
CREATE UNIQUE INDEX jobs_one_synthesis_per_session ON jobs(session_id)
WHERE job_type = 'session_synthesis';

-- Generated hypotheses keep what would test them alongside their evidence links.
ALTER TABLE hypotheses
    ADD COLUMN missing_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN next_steps jsonb NOT NULL DEFAULT '[]'::jsonb;
CREATE INDEX hypotheses_session ON hypotheses(session_id, created_at);
CREATE INDEX hypothesis_support_hypothesis ON hypothesis_support(hypothesis_id);

-- Scout decisions record which branches they created and why others were dropped.
ALTER TABLE agent_decisions
    ADD COLUMN details jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX agent_decisions_session ON agent_decisions(session_id, created_at);

-- A session's paper network can grow after research: expansion jobs follow citations
-- and search deeper, adding papers found but not read.
ALTER TABLE jobs DROP CONSTRAINT jobs_job_type_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_job_type_check CHECK (
    job_type IN (
        'research_session',
        'branch_continue',
        'session_synthesis',
        'network_expansion',
        'claim_extraction',
        'claim_validation',
        'export'
    )
);
-- One expansion at a time per session, so repeated clicks cannot queue several.
CREATE UNIQUE INDEX jobs_one_active_expansion ON jobs(session_id)
WHERE job_type = 'network_expansion' AND status IN ('queued', 'running', 'paused');

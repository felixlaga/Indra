-- Accounts: password sign-in, revocable sign-in sessions, and session ownership.
ALTER TABLE users ADD COLUMN password_hash text;

-- Only a SHA-256 of each sign-in token is stored.
CREATE TABLE user_sessions (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    expires_at timestamptz NOT NULL
);
CREATE INDEX user_sessions_user ON user_sessions(user_id);

-- Sessions without a project still need an owner, so ownership is stored on both.
ALTER TABLE research_sessions ADD COLUMN user_id uuid REFERENCES users(id) ON DELETE CASCADE;
UPDATE research_sessions s SET user_id = p.user_id
FROM projects p WHERE p.id = s.project_id AND p.user_id IS NOT NULL;
CREATE INDEX projects_user ON projects(user_id, created_at DESC);
CREATE INDEX research_sessions_user ON research_sessions(user_id, created_at DESC);

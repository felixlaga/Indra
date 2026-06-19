"use client";

import { ChangeEvent, FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { erlaApi } from "@/lib/api";

interface SessionCreateFormProps {
  projectId: string;
}

export function SessionCreateForm({ projectId }: SessionCreateFormProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<string[]>(["semantic_scholar", "arxiv"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleProvider(provider: string) {
    setProviders((current) =>
      current.includes(provider)
        ? current.filter((item) => item !== provider)
        : [...current, provider],
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const initialQuery = query.trim();
    if (!initialQuery || providers.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const session = await erlaApi.createSession({
        project_id: projectId,
        initial_query: initialQuery,
        source_providers: providers,
      });
      router.push(`/sessions/${session.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Session creation failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="session-create-card" onSubmit={submit}>
      <div>
        <p className="eyebrow">Start a research run</p>
        <h2>Define the question ERLA should map</h2>
      </div>
      <textarea
        value={query}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setQuery(event.target.value)}
        placeholder="Which small-scale dark-matter structures leave observable wave-optics signatures in gravitational-wave signals?"
        rows={4}
        required
      />
      <div className="provider-row" aria-label="Source providers">
        {["semantic_scholar", "arxiv"].map((provider) => (
          <label className="provider-toggle" key={provider}>
            <input
              type="checkbox"
              checked={providers.includes(provider)}
              onChange={() => toggleProvider(provider)}
            />
            <span>{provider.replaceAll("_", " ")}</span>
          </label>
        ))}
      </div>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="session-create-footer">
        <p>Runs are queued through the Phase 3 job contract; API requests remain non-blocking.</p>
        <button
          className="button button-primary"
          type="submit"
          disabled={saving || !query.trim() || providers.length === 0}
        >
          {saving ? "Creating session…" : "Create session"}
        </button>
      </div>
    </form>
  );
}

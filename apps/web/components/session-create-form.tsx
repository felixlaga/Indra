"use client";

import { ChangeEvent, FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { indraApi } from "@/lib/api";
import {
  DEFAULT_DEPTH,
  DEPTH_PRESETS,
  depthPreset,
  maxPapers,
} from "@/lib/research-depth.js";

interface SessionCreateFormProps {
  projectId: string;
}

export function SessionCreateForm({ projectId }: SessionCreateFormProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<string[]>(["arxiv"]);
  const [depth, setDepth] = useState(DEFAULT_DEPTH);
  const preset = depthPreset(depth);
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
      const session = await indraApi.createSession({
        project_id: projectId,
        initial_query: initialQuery,
        source_providers: providers,
        parameters: { research: preset.research },
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
        <h2>Define the question Indra should map</h2>
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
      <fieldset className="depth-picker">
        <legend>Research depth</legend>
        <div className="depth-options">
          {DEPTH_PRESETS.map((option) => (
            <label className="depth-option" key={option.id}>
              <input
                type="radio"
                name="research-depth"
                value={option.id}
                checked={depth === option.id}
                onChange={() => setDepth(option.id)}
              />
              <span>
                <strong>{option.label}</strong>
                <small>{option.description}</small>
              </span>
            </label>
          ))}
        </div>
        <p className="depth-hint">
          Reads up to {maxPapers(preset)} papers and uses at most{" "}
          {String(preset.research.max_model_calls)} model calls. Without a model
          key, every depth runs as Quick and claims are left for review.
        </p>
      </fieldset>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="session-create-footer">
        <p>The session opens on its dashboard, where you can start the run.</p>
        <button
          className="button button-primary"
          type="submit"
          disabled={saving || !query.trim() || providers.length === 0}
        >
          {saving ? "Creating session..." : "Create session"}
        </button>
      </div>
    </form>
  );
}

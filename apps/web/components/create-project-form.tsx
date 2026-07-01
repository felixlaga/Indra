"use client";

import { ChangeEvent, FormEvent, useState } from "react";

import { indraApi } from "@/lib/api";
import type { Project } from "@/lib/types";

interface CreateProjectFormProps {
  onCreated: (project: Project) => void;
}

export function CreateProjectForm({ onCreated }: CreateProjectFormProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [field, setField] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTitle = title.trim();
    if (!normalizedTitle) return;
    setSaving(true);
    setError(null);
    try {
      const project = await indraApi.createProject({
        title: normalizedTitle,
        description: description.trim() || null,
        field: field.trim() || null,
      });
      onCreated(project);
      setTitle("");
      setDescription("");
      setField("");
      setOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Project creation failed");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="button button-primary" type="button" onClick={() => setOpen(true)}>
        New project
      </button>
    );
  }

  return (
    <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
      <div className="modal-header">
        <div>
          <p className="eyebrow">New workspace</p>
          <h2 id="create-project-title">Create a research project</h2>
        </div>
        <button className="icon-button" type="button" onClick={() => setOpen(false)} aria-label="Close">
          Close
        </button>
      </div>
      <form className="form-stack" onSubmit={submit}>
        <label>
          <span>Project title</span>
          <input
            autoFocus
            value={title}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setTitle(event.target.value)}
            placeholder="Wave-optics gravitational-wave lensing"
            required
          />
        </label>
        <label>
          <span>Research field</span>
          <input
            value={field}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setField(event.target.value)}
            placeholder="Cosmology"
          />
        </label>
        <label>
          <span>Description</span>
          <textarea
            value={description}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setDescription(event.target.value)}
            placeholder="Define the long-lived scope of this research workspace."
            rows={4}
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <div className="form-actions">
          <button className="button button-secondary" type="button" onClick={() => setOpen(false)}>
            Cancel
          </button>
          <button className="button button-primary" type="submit" disabled={saving || !title.trim()}>
            {saving ? "Creating..." : "Create project"}
          </button>
        </div>
      </form>
    </section>
  );
}

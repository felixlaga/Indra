"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { authApi, indraApi } from "@/lib/api";

/** Only same-site paths may be used as the post-sign-in destination. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/projects";
}

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [signupOpen, setSignupOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Already signed in, or accounts are off: there is nothing to sign in to.
    fetch("/api/indra/auth/me", { cache: "no-store" })
      .then(async (response) => {
        const status = await response.json().catch(() => ({}));
        if (response.ok) router.replace(next);
        else setSignupOpen(Boolean(status.signup_open));
      })
      .catch(() => setError("The Indra API is not reachable."));
  }, [next, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await authApi.login(email, password);
      else await authApi.register(email, password, name);
      router.replace(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <section className="modal-card login-card">
      <div className="modal-header">
        <div>
          <p className="eyebrow">Indra</p>
          <h1>{mode === "login" ? "Sign in" : "Create your account"}</h1>
        </div>
      </div>
      <form className="form-stack" onSubmit={submit}>
        {mode === "register" && (
          <label>
            <span>Name (optional)</span>
            <input
              value={name}
              autoComplete="name"
              onChange={(event: ChangeEvent<HTMLInputElement>) => setName(event.target.value)}
            />
          </label>
        )}
        <label>
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="email"
            autoFocus
            required
            onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.target.value)}
          />
        </label>
        <label>
          <span>Password{mode === "register" ? " (at least 10 characters)" : ""}</span>
          <input
            type="password"
            value={password}
            minLength={mode === "register" ? 10 : undefined}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            onChange={(event: ChangeEvent<HTMLInputElement>) => setPassword(event.target.value)}
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <div className="form-actions login-actions">
          {signupOpen && (
            <button
              className="button button-secondary"
              type="button"
              disabled={busy}
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
            >
              {mode === "login" ? "Create an account" : "I have an account"}
            </button>
          )}
          <button className="button button-primary" type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </div>
      </form>
    </section>
  );
}

/** Signed-in account and sign-out, shown only when accounts are enabled. */
export function AccountMenu() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    indraApi
      .getAuthStatus()
      .then((status) => setEmail(status.mode === "accounts" ? status.user?.email ?? null : null))
      .catch(() => setEmail(null));
  }, []);

  if (!email) return null;
  return (
    <span className="account-menu">
      <span title={email}>{email}</span>
      <button
        className="button button-secondary button-small"
        type="button"
        onClick={() => void authApi.logout().then(() => router.replace("/login"))}
      >
        Sign out
      </button>
    </span>
  );
}

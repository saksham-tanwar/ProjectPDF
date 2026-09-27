import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Code2, FileText, Quote } from "lucide-react";
import { Link, Navigate, useLocation, useSearchParams } from "react-router";

import { api, googleLoginUrl } from "../api/client";
import { keys, useConfig, useMe } from "../api/queries";
import { Brand } from "../components/Brand";
import { FullPageSpinner, Spinner } from "../components/Feedback";

const ERRORS: Record<string, string> = {
  google: "Google sign-in didn't complete. Please try again.",
  unverified: "Your Google account's email address needs to be verified before you can sign in.",
};

export function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

export function LoginPage() {
  const me = useMe();
  const config = useConfig();
  const queryClient = useQueryClient();
  const location = useLocation();
  const [params] = useSearchParams();
  const error = ERRORS[params.get("error") ?? ""];

  const devLogin = useMutation({
    mutationFn: api.devLogin,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.me }),
  });

  if (me.isPending || config.isPending) return <FullPageSpinner label="Loading" />;
  if (me.data) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from.startsWith("/") ? from : "/"} replace />;
  }

  const options = config.data;
  const noSignIn = options && !options.google_enabled && !options.dev_login_enabled;

  return (
    <div className="login">
      <section className="login-story" aria-hidden>
        <Brand />
        <div className="login-story-body">
          <h2>Ask your PDFs, and see exactly where the answer came from.</h2>
          <div className="login-preview">
            <div className="preview-question">What is the warranty period?</div>
            <div className="preview-answer">
              <p>Manufacturing defects are covered for two years from the date of purchase [p. 4].</p>
              <span className="source-chip">
                <Quote size={12} aria-hidden /> Page 4
              </span>
            </div>
          </div>
        </div>
        <p className="login-story-foot">
          <FileText size={16} /> Contracts, manuals, research papers, reports.
        </p>
      </section>

      <main className="login-panel">
        <div className="login-card">
          <div className="login-brand-small">
            <Brand />
          </div>
          <h1>Sign in to Paperchat</h1>
          <p className="muted">Your documents stay private to your account.</p>

          {error && (
            <p className="notice notice-error" role="alert">
              <CircleAlert size={16} aria-hidden /> {error}
            </p>
          )}
          {(config.isError || devLogin.isError) && (
            <p className="notice notice-error" role="alert">
              <CircleAlert size={16} aria-hidden /> {(config.error ?? devLogin.error)?.message}
            </p>
          )}

          <div className="login-actions">
            {options?.google_enabled && (
              <a className="button button-google" href={googleLoginUrl}>
                <GoogleLogo /> Continue with Google
              </a>
            )}
            {options?.dev_login_enabled && (
              <button type="button" className="button button-secondary" onClick={() => devLogin.mutate()} disabled={devLogin.isPending}>
                {devLogin.isPending ? <Spinner size={16} /> : <Code2 size={16} aria-hidden />} Continue as local developer
              </button>
            )}
            {noSignIn && (
              <p className="notice notice-warn">Sign-in isn't configured on this server yet. Set up Google sign-in to continue.</p>
            )}
          </div>

          <p className="login-legal">
            By continuing you agree to how we handle your data, described in our <Link to="/privacy">privacy notice</Link>.
          </p>
        </div>
      </main>
    </div>
  );
}

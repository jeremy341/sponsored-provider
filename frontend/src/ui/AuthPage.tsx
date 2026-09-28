import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { ApiError, api } from "../lib/api";

type AuthMode = "login" | "signup";

function inviteFromFragment(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("invite");
}

export function AuthPage() {
  const navigate = useNavigate();
  const invite = inviteFromFragment();
  const [mode, setMode] = useState<AuthMode>(invite ? "signup" : "login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isSignup = mode === "signup";

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);

    try {
      const result = isSignup
        ? await api.localSignup({ username: username.trim(), password, invite: invite ?? "" })
        : await api.localLogin({ username: username.trim(), password });

      if (isSignup) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);

      navigate(result.role === "operator" ? "/operator" : "/developer", { replace: true });
    } catch (caught) {
      // Credential prompts stay generic; transport failures keep their explicit message.
      setError(isSignup
        ? caught instanceof ApiError ? caught.message : "Account creation failed. Check the invitation and try again."
        : caught instanceof ApiError ? caught.message : "Invalid username or password");
    } finally {
      setBusy(false);
    }
  }

  return <main className="session-screen auth-screen">
    <div className="auth-stars" aria-hidden="true" />
    <div className="session-mark auth-mark"><span className="brand-mark" aria-hidden="true" /> sponsored<span className="brand-dot">_</span>provider</div>
    <section className="auth-panel" aria-labelledby="auth-title">
      <div className="auth-heading"><span className="auth-icon"><LockKeyhole size={18} aria-hidden="true" /></span><h1 id="auth-title">{isSignup ? "Create your account" : "Console sign in"}</h1><p>{isSignup ? "Choose the username for your new provider account." : "Sign in to your sponsored provider workspace."}</p></div>
      <div className="auth-mode" aria-label="Account access">
        <button type="button" className={!isSignup ? "selected" : ""} aria-label="Switch to sign in" aria-pressed={!isSignup} onClick={() => { setMode("login"); setError(null); }}>Sign in</button>
        <button type="button" className={isSignup ? "selected" : ""} aria-label="Switch to account creation" aria-pressed={isSignup} onClick={() => { setMode("signup"); setError(null); }}>Create account</button>
      </div>
      <form className="auth-form" onSubmit={(event) => { void submit(event); }}>
        {isSignup && !invite && <p className="auth-invite-help">An invitation link is required to create an account. Ask an operator for a link.</p>}
        <label htmlFor="auth-username">Username</label>
        <input id="auth-username" name="username" autoComplete="username" autoCapitalize="none" required maxLength={64} value={username} onChange={(event) => setUsername(event.target.value)} />
        <label htmlFor="auth-password">Password</label>
        <div className="auth-password"><input id="auth-password" name="password" type={revealed ? "text" : "password"} autoComplete={isSignup ? "new-password" : "current-password"} required value={password} onChange={(event) => setPassword(event.target.value)} /><button type="button" className="auth-reveal" aria-label={revealed ? "Hide password" : "Show password"} onClick={() => setRevealed((value) => !value)}>{revealed ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="button button-primary auth-submit" type="submit" disabled={busy || (isSignup && !invite)}>{busy ? isSignup ? "Creating account…" : "Signing in…" : isSignup ? "Create account" : "Sign in"}</button>
        <div className="sr-only" aria-live="polite">{busy ? "Request in progress" : ""}</div>
      </form>
      <p className="auth-footnote">Sessions are protected by secure, same-origin cookies.</p>
    </section>
  </main>;
}

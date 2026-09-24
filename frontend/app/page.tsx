"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { ApiError, login } from "@/lib/api";
import { loadSession, roleLabel, saveSession } from "@/lib/session";

import styles from "./login.module.css";

const DEMO_ACCOUNTS = [
  { username: "dr.mehta", role: "doctor" },
  { username: "nurse.priya", role: "nurse" },
  { username: "billing.ravi", role: "billing_executive" },
  { username: "tech.anand", role: "technician" },
  { username: "admin.sys", role: "admin" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (loadSession()) router.replace("/chat");
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(username.trim(), password);
      saveSession(res);
      router.push("/chat");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.wrap}>
      <section className={styles.card} aria-labelledby="login-title">
        <div className={styles.brand}>
          <span className={styles.logo} aria-hidden>
            ✚
          </span>
          <div>
            <h1 id="login-title">MediBot</h1>
            <p className={styles.tagline}>MediAssist Health Network · internal knowledge assistant</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className={styles.form}>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className={styles.demo}>
          <h2>Demo accounts</h2>
          <p className={styles.hint}>
            Click an account to fill the username. The demo password is configured on the backend
            (<code>DEMO_PASSWORD</code>) — see the README.
          </p>
          <ul>
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.username}>
                <button
                  type="button"
                  className={styles.demoBtn}
                  onClick={() => setUsername(a.username)}
                  aria-label={`Use ${a.username} (${roleLabel(a.role)})`}
                >
                  <span className={styles.demoUser}>{a.username}</span>
                  <span className="badge badge-muted">{roleLabel(a.role)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </main>
  );
}

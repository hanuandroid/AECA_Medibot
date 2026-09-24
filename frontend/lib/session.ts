import type { LoginResponse, Session } from "./types";

const KEY = "medibot.session";

// --- external-store plumbing so React can subscribe to the stored session ---------------------
const listeners = new Set<() => void>();
let cachedRaw: string | null = null;
let cachedSession: Session | null = null;

function notify(): void {
  listeners.forEach((l) => l());
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** Stable snapshot for useSyncExternalStore (same object until storage changes). */
export function sessionSnapshot(): Session | null {
  let raw: string | null = null;
  try {
    raw = sessionStorage.getItem(KEY);
  } catch {
    raw = null;
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedSession = raw ? parseSession(raw) : null;
  }
  if (cachedSession && new Date(cachedSession.expiresAt).getTime() <= Date.now()) return null;
  return cachedSession;
}

function parseSession(raw: string): Session | null {
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function saveSession(res: LoginResponse): Session {
  const session: Session = {
    token: res.access_token,
    username: res.username,
    displayName: res.display_name,
    role: res.role,
    expiresAt: res.expires_at,
  };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* storage unavailable (private mode) */
  }
  notify();
  return session;
}

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (new Date(session.expiresAt).getTime() <= Date.now()) {
      clearSession();
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  notify();
}

export const ROLE_LABELS: Record<string, string> = {
  doctor: "Doctor",
  nurse: "Nurse",
  billing_executive: "Billing Executive",
  technician: "Technician",
  admin: "Admin",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

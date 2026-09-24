import type { CollectionsResponse, Session } from "@/lib/types";
import { roleLabel, titleCase } from "@/lib/session";

import styles from "./chat.module.css";

interface Props {
  session: Session;
  access: CollectionsResponse | null;
  onLogout: () => void;
}

export function AccessPanel({ session, access, onLogout }: Props) {
  return (
    <aside className={styles.sidebar} aria-label="Your access">
      <div className={styles.userBox}>
        <div className={styles.avatar} aria-hidden>
          {session.displayName.charAt(0).toUpperCase()}
        </div>
        <div>
          <div className={styles.userName}>{session.displayName}</div>
          <div className={styles.userHandle}>{session.username}</div>
        </div>
      </div>

      <div className={styles.roleRow}>
        <span className={styles.label}>Role</span>
        <span className={`badge ${styles.roleBadge}`}>{roleLabel(session.role)}</span>
      </div>

      {access ? (
        <>
          <h2 className={styles.sectionTitle}>Accessible collections</h2>
          <ul className={styles.collList}>
            {access.collections.map((c) => (
              <li key={c.name} className={styles.allowed} title={c.label}>
                <span aria-hidden>✓</span> {titleCase(c.name)}
              </li>
            ))}
          </ul>

          <h2 className={styles.sectionTitle}>Restricted</h2>
          {access.restricted.length === 0 ? (
            <p className={styles.none}>None — full access</p>
          ) : (
            <ul className={styles.collList}>
              {access.restricted.map((c) => (
                <li key={c.name} className={styles.restricted} title={c.label}>
                  <span aria-hidden>✕</span> {titleCase(c.name)}
                </li>
              ))}
            </ul>
          )}

          <h2 className={styles.sectionTitle}>Analytics (SQL RAG)</h2>
          <p className={access.can_use_sql ? styles.allowed : styles.restricted}>
            {access.can_use_sql
              ? "✓ Claims & maintenance database"
              : "✕ Not available for this role"}
          </p>
        </>
      ) : (
        <p className={styles.none}>Loading permissions…</p>
      )}

      <p className={styles.note}>
        Access is enforced by the server inside every vector-database query — not by this page.
      </p>

      <button type="button" className="btn btn-ghost" onClick={onLogout}>
        Sign out
      </button>
    </aside>
  );
}

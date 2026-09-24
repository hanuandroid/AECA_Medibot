import type { ChatResponse } from "@/lib/types";
import { roleLabel, titleCase } from "@/lib/session";

import styles from "./chat.module.css";

export type Message =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "bot"; response: ChatResponse }
  | { id: string; kind: "error"; text: string };

function RetrievalBadge({ response }: { response: ChatResponse }) {
  const isSql = response.retrieval_type === "sql_rag";
  return (
    <span className={`badge ${isSql ? "badge-sql" : "badge-hybrid"}`}>
      {isSql ? "SQL RAG" : "Hybrid RAG"}
    </span>
  );
}

function Sources({ response }: { response: ChatResponse }) {
  if (response.access_denied) return null; // nothing was retrieved or queried
  if (response.retrieval_type === "sql_rag") {
    return (
      <p className={styles.sourceNote}>
        Source: MediAssist operations database (claims / maintenance_tickets)
        {typeof response.sql_row_count === "number" ? ` · ${response.sql_row_count} row(s)` : ""}
      </p>
    );
  }
  if (response.sources.length === 0) return null;
  return (
    <div className={styles.sources}>
      <h3>Sources</h3>
      <ol>
        {response.sources.map((s, i) => (
          <li key={`${s.source_document}-${s.section_title}-${i}`}>
            <span className={styles.sourceDoc}>{s.source_document}</span>
            <span className={styles.sourceSep} aria-hidden>
              ›
            </span>
            <span>{s.section_title}</span>
            <span className="badge badge-muted">{titleCase(s.collection)}</span>
            {s.page_numbers && s.page_numbers.length > 0 && (
              <span className={styles.page}>p. {s.page_numbers.join(", ")}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

function RetrievalDetails({ response }: { response: ChatResponse }) {
  if (response.retrieval_type === "sql_rag" && response.sql) {
    return (
      <details className={styles.details}>
        <summary>Generated SQL</summary>
        <pre>{response.sql}</pre>
      </details>
    );
  }
  if (response.candidates.length === 0) return null;
  return (
    <details className={styles.details}>
      <summary>Retrieval details: hybrid candidates → cross-encoder rerank</summary>
      <table>
        <thead>
          <tr>
            <th scope="col">Hybrid rank</th>
            <th scope="col">Rerank</th>
            <th scope="col">Score</th>
            <th scope="col">Chunk</th>
            <th scope="col">To LLM</th>
          </tr>
        </thead>
        <tbody>
          {response.candidates.map((c) => (
            <tr key={`${c.initial_rank}`} className={c.sent_to_llm ? styles.used : undefined}>
              <td>#{c.initial_rank}</td>
              <td>{c.final_rank ? `#${c.final_rank}` : "–"}</td>
              <td>{c.rerank_score?.toFixed(2) ?? "–"}</td>
              <td>
                {c.source_document} › {c.section_title}
              </td>
              <td>{c.sent_to_llm ? "✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export function MessageView({ message }: { message: Message }) {
  if (message.kind === "user") {
    return (
      <div className={`${styles.msg} ${styles.user}`}>
        <p>{message.text}</p>
      </div>
    );
  }
  if (message.kind === "error") {
    return (
      <div className={`${styles.msg} ${styles.bot}`} role="alert">
        <p className="error">{message.text}</p>
      </div>
    );
  }
  const r = message.response;
  return (
    <article
      className={`${styles.msg} ${styles.bot} ${r.access_denied ? styles.denied : ""}`}
      aria-label="MediBot answer"
    >
      <header className={styles.msgHeader}>
        <span className={styles.botName}>MediBot</span>
        <RetrievalBadge response={r} />
        {r.access_denied && <span className="badge badge-denied">Access restricted</span>}
        {!r.llm_used && !r.access_denied && (
          <span className="badge badge-muted">LLM unavailable</span>
        )}
      </header>
      {r.access_denied ? (
        <div className={styles.denialBox}>
          <strong>🔒 Blocked by role-based access control</strong>
          <p>{r.answer}</p>
          {r.denied_collections.length > 0 && (
            <p className={styles.denialMeta}>
              Requested: {r.denied_collections.join(", ")} · Your role ({roleLabel(r.role)}) can
              access: {r.accessible_collections.join(", ")}
            </p>
          )}
        </div>
      ) : (
        <div className={styles.answer}>{r.answer}</div>
      )}
      {!r.access_denied && r.denied_collections.length > 0 && (
        <p className={styles.partialNote}>
          Parts of this question concern {r.denied_collections.join(", ")} documents, which were
          excluded for your role.
        </p>
      )}
      <Sources response={r} />
      <RetrievalDetails response={r} />
    </article>
  );
}

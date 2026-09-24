// Mirrors backend/app/api/schemas.py

export type RetrievalType = "hybrid_rag" | "sql_rag";

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  username: string;
  display_name: string;
  role: string;
  collections: string[];
}

export interface CollectionInfo {
  name: string;
  label: string;
}

export interface CollectionsResponse {
  role: string;
  role_label: string;
  collections: CollectionInfo[];
  restricted: CollectionInfo[];
  can_use_sql: boolean;
}

export interface Source {
  source_document: string;
  section_title: string;
  collection: string;
  chunk_type?: string | null;
  page_numbers?: number[];
  rerank_score?: number | null;
}

export interface RankedCandidate {
  source_document: string;
  section_title: string;
  collection: string;
  initial_rank: number;
  fusion_score: number;
  rerank_score: number | null;
  final_rank: number | null;
  sent_to_llm: boolean;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  retrieval_type: RetrievalType;
  role: string;
  access_denied: boolean;
  denied_collections: string[];
  accessible_collections: string[];
  route_method?: string | null;
  llm_used: boolean;
  sql?: string | null;
  sql_row_count?: number | null;
  candidates: RankedCandidate[];
}

export interface Session {
  token: string;
  username: string;
  displayName: string;
  role: string;
  expiresAt: string;
}

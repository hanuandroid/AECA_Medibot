import type { ChatResponse, CollectionsResponse, LoginResponse } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(`Cannot reach the MediBot API at ${API_URL}. Is the backend running?`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = "Invalid request";
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getCollections(role: string, token: string): Promise<CollectionsResponse> {
  return request<CollectionsResponse>(`/collections/${encodeURIComponent(role)}`, {}, token);
}

// Only the question is sent. The role is derived server-side from the token.
export function chat(question: string, token: string): Promise<ChatResponse> {
  return request<ChatResponse>(
    "/chat",
    { method: "POST", body: JSON.stringify({ question }) },
    token,
  );
}

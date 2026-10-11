import type { DocumentDetails, DocumentSummary, HealthStatus } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/api/documents`);
  if (!res.ok) {
    throw new Error(`Failed to load documents: HTTP ${res.status}`);
  }
  const data = await res.json();
  return data.documents || [];
}

export async function fetchDocumentDetails(
  fileName: string,
  userId: string = "guest_01"
): Promise<DocumentDetails> {
  const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(fileName)}?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) {
    throw new Error(`Failed to load document details: HTTP ${res.status}`);
  }
  return res.json();
}

export interface ChatRequestPayload {
  query: string;
  user_id?: string;
  mode?: "GLOBAL_QA" | "LOCAL_QA" | "LEARNING";
  target_file?: string;
  target_section?: string;
}

export interface ChatResponsePayload {
  content: string;
  metadata?: Record<string, unknown>;
}

export async function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponsePayload> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query: payload.query,
      user_id: payload.user_id || "guest_01",
      mode: payload.mode || "GLOBAL_QA",
      target_file: payload.target_file || "",
      target_section: payload.target_section || "",
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Chat request failed: ${res.status}`);
  }

  return res.json();
}

export async function uploadDocument(file: File): Promise<{ status: string; file_name: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorData.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

export async function deleteDocument(fileName: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete document: HTTP ${res.status}`);
  }
}

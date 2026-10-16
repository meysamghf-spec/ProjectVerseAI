export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * API origin. Empty string = same origin (production behind the shared Caddy, which routes /api/* to the API).
 * Unset = the local development API on port 8000.
 */
export function apiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  return configured === undefined ? "http://localhost:8000" : configured.replace(/\/$/, "");
}

function authHeaders(): Record<string, string> {
  // Required by the API for cookie-authenticated writes (CSRF defence; cross-site forms cannot set it).
  const headers: Record<string, string> = { "X-Requested-With": "XMLHttpRequest" };
  if (typeof window === "undefined") {
    return headers;
  }
  // Only honoured by a development-mode API. Production ignores it and uses the session cookie.
  headers["X-Owner-Id"] = window.localStorage.getItem("projectverse.owner") || "dev-user";
  return headers;
}

export const UNAUTHORIZED_EVENT = "projectverse:unauthorized";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers || {}),
    },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/v1/auth/")) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    const message =
      typeof payload === "object" && payload && "error" in payload
        ? String((payload as { error?: { message?: string } }).error?.message || response.statusText)
        : response.statusText;
    throw new ApiError(response.status, message);
  }
  return payload as T;
}

export async function downloadReport(projectId: string, format: string, reportType: string): Promise<void> {
  const response = await fetch(`${apiBase()}/api/v1/projects/${projectId}/reports`, {
    method: "POST",
    credentials: "include",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ format, report_type: reportType }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message || "The report could not be generated.";
    throw new ApiError(response.status, message);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || `projectverse-report.${format === "xlsx" ? "xlsx" : format}`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

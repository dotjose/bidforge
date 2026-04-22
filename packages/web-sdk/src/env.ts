/**
 * Public env for the browser SDK — never read server-only secrets here.
 */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) {
    if (process.env.NEXT_PUBLIC_ENV === "production") {
      throw new Error(
        "NEXT_PUBLIC_API_BASE_URL must be set when NEXT_PUBLIC_ENV=production",
      );
    }
    return "http://localhost:8000";
  }
  // Same-origin API (e.g. `/api` on the Next host). Paths must be absolute from site root.
  if (raw.startsWith("/")) {
    return "";
  }
  return raw.replace(/\/$/, "");
}

export function getPublicEnv(): string {
  return process.env.NEXT_PUBLIC_ENV?.trim() || "development";
}

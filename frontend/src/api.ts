export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
let csrf = "";
export async function refreshCsrf() {
  const response = await fetch("/api/v1/auth/csrf/", {
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new ApiError(response.status, "Could not establish CSRF protection.");
  csrf = (await response.json()).csrfToken;
}
export async function api<T>(
  path: string,
  method = "GET",
  payload?: unknown,
): Promise<T> {
  if (method !== "GET" && !csrf) await refreshCsrf();
  const response = await fetch(`/api/v1/${path}`, {
    method,
    credentials: "same-origin",
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      [
        data.error?.message ?? "Request failed.",
        data.error?.details && Object.keys(data.error.details).length
          ? JSON.stringify(data.error.details)
          : "",
      ]
        .filter(Boolean)
        .join(" "),
    );
  if (path === "auth/login/" || path === "auth/register/") await refreshCsrf();
  return data as T;
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface User {
  email: string;
  membership: null | { role: "ADMIN" | "STAFF" };
}
export interface Organization {
  name: string;
  currency: string;
}
export interface Category {
  id: string;
  name: string;
  is_active: boolean;
}
export interface Product {
  id: string;
  name: string;
  variant_count: number;
  is_available: boolean;
}
export interface Stock {
  variant_id: string;
  product_name: string;
  sku: string;
  size: string;
  color: string;
  quantity: number;
  price: string;
  is_available: boolean;
}
export interface Sale {
  id: string;
  total: string;
  currency: string;
  created_at: string;
  status: string;
  items: {
    sku: string;
    quantity: number;
    unit_price: string;
    subtotal: string;
  }[];
}
export interface Movement {
  id: string;
  variant_id: string;
  delta: number;
  reason: string;
  created_at: string;
}
export function pagePath(url: string): string {
  const parsed = new URL(url, window.location.origin);
  if (!parsed.pathname.startsWith("/api/v1/"))
    throw new Error("Invalid pagination URL");
  return parsed.pathname.slice("/api/v1/".length) + parsed.search;
}

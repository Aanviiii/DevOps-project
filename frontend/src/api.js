// Thin wrapper around fetch for the Shelfwise API. Every call goes to the same origin
// under /api; nginx (or the Vite dev server) forwards it to the backend.

export class ApiError extends Error {
  constructor(status, code, detail) {
    super(detail);
    this.status = status;
    this.code = code;
  }
}

let backendVersion = null;
export const getBackendVersion = () => backendVersion;

async function request(path, { method = "GET", body, params } = {}) {
  const url = new URL(`/api${path}`, window.location.origin);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the Shelfwise API. Is the backend running?");
  }

  backendVersion = response.headers.get("X-Shelfwise-Version") ?? backendVersion;
  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // FastAPI validation errors arrive as a list; lending-rule refusals as {code, detail}.
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ")
      : data?.detail ?? `Request failed (${response.status})`;
    throw new ApiError(response.status, data?.code ?? "HTTP_ERROR", detail);
  }
  return data;
}

export const api = {
  books: {
    list: (params) => request("/books", { params }),
    genres: () => request("/books/genres"),
    create: (body) => request("/books", { method: "POST", body }),
    update: (id, body) => request(`/books/${id}`, { method: "PUT", body }),
    remove: (id) => request(`/books/${id}`, { method: "DELETE" }),
  },
  members: {
    list: (params) => request("/members", { params }),
    account: (id) => request(`/members/${id}/account`),
    create: (body) => request("/members", { method: "POST", body }),
    update: (id, body) => request(`/members/${id}`, { method: "PUT", body }),
    remove: (id) => request(`/members/${id}`, { method: "DELETE" }),
    settleFines: (id) => request(`/members/${id}/settle-fines`, { method: "POST" }),
  },
  loans: {
    list: (params) => request("/loans", { params }),
    checkout: (bookId, memberId) =>
      request("/loans", { method: "POST", body: { book_id: bookId, member_id: memberId } }),
    giveBack: (id) => request(`/loans/${id}/return`, { method: "POST" }),
    renew: (id) => request(`/loans/${id}/renew`, { method: "POST" }),
  },
  holds: {
    list: (params) => request("/holds", { params }),
    place: (bookId, memberId) =>
      request("/holds", { method: "POST", body: { book_id: bookId, member_id: memberId } }),
    cancel: (id) => request(`/holds/${id}/cancel`, { method: "POST" }),
  },
  stats: () => request("/stats"),
};

export const API_BASE = "https://forge-bot-isu2.onrender.com";

export async function fetchJson(url, options = {}) {
  const target = url.startsWith("http://") || url.startsWith("https://") ? url : `${API_BASE}${url}`;
  
  const response = await fetch(target, options);
  const payload = await response.json().catch(() => ({}));
  
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || "Request failed.");
  }
  return payload;
}

export async function fetchAuthedJson(url, session, options = {}) {
  if (!session || !session.access_token) {
    throw new Error("Must be signed in.");
  }
  return fetchJson(url, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${session.access_token}`,
    },
  });
}

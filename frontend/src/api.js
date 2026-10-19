async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
    } catch {
      // Keep the HTTP status message when the response isn't JSON.
    }
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

const json = (body) => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  runs: () => request("/api/runs"),
  run: (id) => request(`/api/runs/${encodeURIComponent(id)}`),
  startRun: (theme) => request("/api/runs", json({ theme_override: theme || null })),
  approve: (id, decisions) =>
    request(`/api/runs/${encodeURIComponent(id)}/approve`, json({ decisions })),
  feedback: (id, body) =>
    request(`/api/runs/${encodeURIComponent(id)}/feedback`, json(body)),
  brand: () => request("/api/brand"),
  memory: (scope, query) =>
    request(`/api/memory/${scope.replace(/^\//, "")}?q=${encodeURIComponent(query)}&limit=30`),
  health: () => request("/api/health"),
};

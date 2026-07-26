// Тонкая обёртка над JSON API бэкенда (web/api.py).
const Api = {
  async _get(path, params) {
    const url = new URL(path, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
      });
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return res.json();
  },

  categories() {
    return this._get("/api/categories");
  },

  services(category) {
    return this._get("/api/services", { category });
  },

  masters(serviceId) {
    return this._get("/api/masters", { service_id: serviceId });
  },

  dates(staffId, serviceId) {
    return this._get("/api/dates", { staff_id: staffId, service_id: serviceId });
  },

  times(staffId, serviceId, date) {
    return this._get("/api/times", { staff_id: staffId, service_id: serviceId, date });
  },

  async book(payload) {
    const res = await fetch("/api/booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    return { ok: res.ok, ...data };
  },
};

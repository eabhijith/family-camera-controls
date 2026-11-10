export const CLOUD_DOMAIN = "hikconnect_cloud_relay";
export const SETUP_URL = "https://my.home-assistant.io/redirect/config_flow_start/?domain=hikconnect_cloud_relay";

export function cloudCameraIds(states = {}) {
  return Object.keys(states).filter((id) => /^camera\.[a-z0-9_]+$/.test(id)
    && states[id]?.attributes?.cloud_provider === CLOUD_DOMAIN).sort();
}

const ElementBase = globalThis.HTMLElement || class {};
export class HikCloudGridCard extends ElementBase {
  setConfig(config) { this._config = config; }
  getCardSize() { return Math.max(3, (this._cards?.length || 0) * 4); }
  set hass(value) {
    this._hass = value;
    this._update();
  }
  connectedCallback() { this._update(); }

  async _update() {
    if (!this._hass || !globalThis.document) return;
    if (!this.shadowRoot) {
      const root = this.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = `:host{display:block}ha-card{padding:16px}p{font-size:16px;line-height:1.55}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}a{display:inline-flex;align-items:center;min-height:56px;padding:0 18px;border-radius:12px;background:var(--primary-color);color:var(--text-primary-color,#fff);text-decoration:none;font-size:16px;font-weight:600;margin-top:12px}a:focus-visible{outline:3px solid var(--primary-text-color);outline-offset:3px}`;
      const outer = document.createElement("ha-card");
      outer.header = "DVR cloud cameras";
      this._notice = document.createElement("p");
      this._grid = document.createElement("div");
      this._grid.className = "grid";
      const setup = document.createElement("a");
      setup.href = SETUP_URL;
      setup.target = "_blank";
      setup.rel = "noopener noreferrer";
      setup.textContent = "Connect a Hik-Connect cloud camera";
      outer.append(this._notice, this._grid, setup);
      root.append(style, outer);
      this._cards = [];
    }
    const ids = cloudCameraIds(this._hass.states);
    this._notice.textContent = ids.length
      ? "Cloud feeds — no connected phone required. Unavailable feeds have not produced a fresh picture."
      : "No cloud cameras configured yet. Sign in once using your Hik-Connect cloud account, not the DVR administrator password. DVR compatibility must still be verified; review the transport warning during setup.";
    const key = ids.join("|");
    if (key !== this._key) {
      this._key = key;
      this._grid.replaceChildren();
      this._cards = [];
      if (ids.length) {
        try {
          const helpers = await window.loadCardHelpers();
          if (key !== this._key) return;
          for (const entity of ids) {
            const card = helpers.createCardElement({ type: "picture-entity", entity,
              camera_view: "live", show_state: true, aspect_ratio: "16:9",
              tap_action: { action: "more-info" }, hold_action: { action: "none" } });
            card.hass = this._hass;
            this._cards.push(card);
            this._grid.append(card);
          }
        } catch {
          this._key = undefined;
          this._notice.textContent = "Camera cards could not load. Refresh the page to retry.";
        }
      }
    }
    for (const card of this._cards) card.hass = this._hass;
  }
}

if (globalThis.customElements && !customElements.get("family-hik-cloud-grid")) {
  customElements.define("family-hik-cloud-grid", HikCloudGridCard);
}

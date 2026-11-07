import { cropRegion } from "./view-geometry.mjs";

/** Authenticated snapshots and explicit lower-lens controls. No camera secrets. */
class FamilyDualLensCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = "both";
    this._fetching = false;
    this._moving = false;
  }

  setConfig(config) {
    if (!/^camera\.[a-z0-9_]+$/.test(config.entity || "")) throw new Error("A camera entity is required");
    for (const entity of Object.values(config.buttons || {})) {
      if (!/^button\.[a-z0-9_]+$/.test(entity)) throw new Error("Invalid direction button entity");
    }
    cropRegion(10, 10, "both", config.split_fraction ?? 0.5);
    this._abort?.abort();
    this._bitmap?.close();
    this._bitmap = null;
    this._config = { ...config };
    this._render();
    if (this.isConnected) this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateControls();
    if (this.isConnected && !this._bitmap) this._refresh();
  }

  getCardSize() { return 6; }

  connectedCallback() {
    this._timer = window.setInterval(() => this._refresh(), 3000);
    this._refresh();
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
    this._abort?.abort();
    this._bitmap?.close();
    this._bitmap = null;
  }

  _render() {
    // User-supplied labels are assigned using textContent, never HTML.
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding:16px; color:var(--primary-text-color); }
        h2 { margin:0 0 12px; font-size:20px; }
        .tabs { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:12px; }
        button { min-height:48px; font:inherit; font-weight:600; cursor:pointer;
          border:1px solid var(--divider-color,#ccc); border-radius:12px;
          color:var(--primary-text-color); background:var(--card-background-color,#fff); }
        button:focus-visible { outline:3px solid var(--primary-color,#1565c0); outline-offset:2px; }
        button[aria-pressed="true"] { background:var(--primary-color,#1565c0); color:var(--text-primary-color,#fff); }
        button:disabled { opacity:.45; cursor:not-allowed; }
        canvas { display:block; width:100%; height:auto; border-radius:12px; background:#111; }
        .status,.note { font-size:14px; line-height:1.5; margin:10px 0; }
        .status { color:var(--secondary-text-color); }
        h3 { font-size:16px; margin:16px 0 10px; }
        .pad { display:grid; grid-template-columns:repeat(3,1fr); grid-template-areas:
          ". up ." "left stop right" ". down ."; gap:8px; }
        .pad button { min-height:64px; }
        [hidden] { display:none !important; }
      </style>
      <ha-card>
        <h2></h2>
        <div class="tabs" role="group" aria-label="Choose displayed camera view">
          <button data-view="both">Both views</button>
          <button data-view="upper">Upper view</button>
          <button data-view="lower">Lower view</button>
        </div>
        <canvas aria-label="Camera snapshot"></canvas>
        <div class="status" role="status" aria-live="polite">Connecting…</div>
        <div class="upper note" hidden>Upper-view movement is not connected. Selecting a view changes only the displayed picture.</div>
        <div class="controls">
          <h3>Lower camera direction</h3>
          <div class="pad">
            <button data-direction="up" style="grid-area:up" aria-label="Move lower camera up">↑ Up</button>
            <button data-direction="left" style="grid-area:left" aria-label="Move lower camera left">← Left</button>
            <button data-direction="stop" style="grid-area:stop" aria-label="Stop lower camera">■ Stop</button>
            <button data-direction="right" style="grid-area:right" aria-label="Move lower camera right">Right →</button>
            <button data-direction="down" style="grid-area:down" aria-label="Move lower camera down">↓ Down</button>
          </div>
        </div>
        <div class="note">Snapshots refresh every 3 seconds. View selection does not move either lens.</div>
      </ha-card>`;
    this.shadowRoot.querySelector("h2").textContent = this._config.name || "Camera";
    for (const button of this.shadowRoot.querySelectorAll("[data-view]")) {
      button.addEventListener("click", () => {
        this._view = button.dataset.view;
        this._draw();
        this._updateControls();
      });
    }
    for (const button of this.shadowRoot.querySelectorAll("[data-direction]")) {
      button.addEventListener("click", () => this._press(button.dataset.direction));
    }
    this._updateControls();
  }

  _updateControls() {
    if (!this._config || !this.shadowRoot.querySelector("canvas")) return;
    const state = this._hass?.states[this._config.entity]?.state;
    const available = state && !["unknown", "unavailable"].includes(state);
    for (const button of this.shadowRoot.querySelectorAll("[data-view]")) {
      button.setAttribute("aria-pressed", String(button.dataset.view === this._view));
    }
    this.shadowRoot.querySelector(".upper").hidden = this._view !== "upper";
    this.shadowRoot.querySelector(".controls").hidden = this._view === "upper" || !this._config.buttons;
    for (const button of this.shadowRoot.querySelectorAll("[data-direction]")) {
      const id = this._config.buttons?.[button.dataset.direction];
      const target = this._hass?.states[id];
      button.disabled = !available || !target || target.state === "unavailable" ||
        (this._moving && button.dataset.direction !== "stop");
    }
    if (!available && state) this._message("Camera disconnected. Check power and Wi-Fi.");
  }

  _message(message) {
    const element = this.shadowRoot.querySelector(".status");
    if (element) element.textContent = message;
  }

  async _refresh() {
    if (!this._hass || !this._config || this._fetching || !this.isConnected || document.hidden) return;
    this._fetching = true;
    const requestedEntity = this._config.entity;
    this._abort = new AbortController();
    const timer = window.setTimeout(() => this._abort.abort(), 10000);
    try {
      const response = await this._hass.fetchWithAuth(`/api/camera_proxy/${requestedEntity}`, {
        signal: this._abort.signal, cache: "no-store",
      });
      if (!response.ok) throw new Error("Snapshot unavailable");
      const bitmap = await createImageBitmap(await response.blob());
      if (!this.isConnected || requestedEntity !== this._config.entity) { bitmap.close(); return; }
      this._bitmap?.close();
      this._bitmap = bitmap;
      this._draw();
      this._message(`Updated ${new Date().toLocaleTimeString()}`);
    } catch {
      if (this.isConnected) this._message("Unable to refresh — the picture may be out of date.");
    } finally {
      window.clearTimeout(timer);
      this._fetching = false;
    }
  }

  _draw() {
    if (!this._bitmap) return;
    const region = cropRegion(this._bitmap.width, this._bitmap.height, this._view, this._config.split_fraction ?? 0.5);
    const canvas = this.shadowRoot.querySelector("canvas");
    canvas.width = region.width;
    canvas.height = region.height;
    canvas.getContext("2d").drawImage(this._bitmap, region.x, region.y, region.width, region.height,
      0, 0, region.width, region.height);
  }

  async _press(direction) {
    const entity = this._config.buttons?.[direction];
    if (!entity || !this._hass || (this._moving && direction !== "stop")) return;
    if (direction !== "stop") this._moving = true;
    this._updateControls();
    try {
      await this._hass.callService("button", "press", { entity_id: entity });
      this._message(direction === "stop" ? "Stop command sent." : "Short movement command sent.");
    } catch {
      this._message("Movement failed. Check camera connection, then try Stop.");
    } finally {
      if (direction !== "stop") this._moving = false;
      this._updateControls();
    }
  }
}

if (!customElements.get("family-dual-lens-card")) customElements.define("family-dual-lens-card", FamilyDualLensCard);
window.customCards = window.customCards || [];
window.customCards.push({ type:"family-dual-lens-card", name:"Family Dual Lens", description:"Separate displayed views and lower-lens controls." });

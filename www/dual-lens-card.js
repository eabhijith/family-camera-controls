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
        :host { --family-accent:#164e63; --family-on-accent:#fff; display:block; min-width:0; max-width:100%; }
        * { box-sizing:border-box; }
        ha-card { display:block; width:100%; min-width:0; padding:20px; color:var(--primary-text-color); font-size:16px; }
        h2 { margin:0 0 16px; font-size:20px; line-height:1.3; }
        .tabs { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-bottom:12px; }
        button { min-width:0; padding:10px 8px; min-height:56px; font:inherit; font-size:16px; font-weight:600; cursor:pointer;
          border:1px solid var(--divider-color,#ccc); border-radius:12px;
          color:var(--primary-text-color); background:var(--card-background-color,#fff); }
        button:focus-visible { outline:3px solid var(--family-accent); outline-offset:3px; }
        button[aria-pressed="true"] { background:var(--family-accent); color:var(--family-on-accent); border-color:var(--family-accent); }
        @media (hover:hover) { button:not(:disabled):hover { box-shadow:inset 0 0 0 2px var(--family-accent); } }
        button:not(:disabled):active { opacity:.8; }
        button:disabled { opacity:.45; cursor:not-allowed; }
        canvas { display:block; width:100%; height:auto; max-height:520px; object-fit:contain; border-radius:12px; background:#111; }
        .status,.note { font-size:16px; line-height:1.5; margin:12px 0; }
        .status { color:var(--secondary-text-color); }
        .timestamp { font-size:14px; color:var(--secondary-text-color); font-variant-numeric:tabular-nums; margin-top:8px; }
        h3 { font-size:18px; margin:20px 0 12px; }
        .pad { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); grid-template-areas:
          ". up ." "left stop right" ". down ."; gap:8px; }
        .pad button { min-height:72px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; }
        .pad svg { width:26px; height:26px; }
        .refresh { width:100%; margin-top:12px; }
        @media (max-width:420px) { ha-card { padding:16px; } .tabs { gap:8px; } }
        @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto; transition:none; } }
        [hidden] { display:none !important; }
      </style>
      <ha-card>
        <h2></h2>
        <div class="tabs" role="group" aria-label="Choose displayed camera view">
          <button data-view="both" aria-label="Show both camera pictures">Both</button>
          <button data-view="upper" aria-label="Show upper camera picture">Upper</button>
          <button data-view="lower" aria-label="Show lower camera picture">Lower</button>
        </div>
        <canvas aria-label="Camera snapshot"></canvas>
        <div class="timestamp">Snapshots · refreshed every 3 seconds</div>
        <div class="status" role="status" aria-live="polite">Connecting…</div>
        <div class="upper note" hidden>Upper-view movement is not connected. Selecting a view changes only the displayed picture.</div>
        <div class="controls">
          <h3>Move the lower camera</h3>
          <div class="pad">
            <button data-direction="up" style="grid-area:up" aria-label="Move lower camera up"><span class="icon"></span><span>Up</span></button>
            <button data-direction="left" style="grid-area:left" aria-label="Move lower camera left"><span class="icon"></span><span>Left</span></button>
            <button data-direction="stop" style="grid-area:stop" aria-label="Stop lower camera"><span class="icon"></span><span>Stop</span></button>
            <button data-direction="right" style="grid-area:right" aria-label="Move lower camera right"><span class="icon"></span><span>Right</span></button>
            <button data-direction="down" style="grid-area:down" aria-label="Move lower camera down"><span class="icon"></span><span>Down</span></button>
          </div>
        </div>
        <button class="refresh">Refresh picture</button>
        <div class="note">Both / Upper / Lower changes the picture only.</div>
      </ha-card>`;
    this.shadowRoot.querySelector("h2").textContent = this._config.name || "Camera";
    const paths = {up:"M12 20V4m-7 7 7-7 7 7",down:"M12 4v16m-7-7 7 7 7-7",
      left:"M20 12H4m7-7-7 7 7 7",right:"M4 12h16m-7-7 7 7-7 7"};
    for (const button of this.shadowRoot.querySelectorAll("[data-direction]")) {
      const direction = button.dataset.direction;
      button.querySelector(".icon").innerHTML = direction === "stop"
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor"/></svg>'
        : `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[direction]}"/></svg>`;
    }
    this.shadowRoot.querySelector(".refresh").addEventListener("click", () => this._refresh());
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
    if (element && element.textContent !== message) element.textContent = message;
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
      this.shadowRoot.querySelector(".timestamp").textContent = `Snapshot updated ${new Date().toLocaleTimeString()} · every 3 seconds`;
      if (this.shadowRoot.querySelector(".status").textContent === "Connecting…" || this._refreshFailed) this._message("Picture connected.");
      this._refreshFailed = false;
    } catch {
      this._refreshFailed = true;
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

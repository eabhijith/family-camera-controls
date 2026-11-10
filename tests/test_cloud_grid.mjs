import assert from "node:assert/strict";
import test from "node:test";
import { cloudCameraIds, SETUP_URL } from "../www/hik-cloud-grid-card.js";

test("setup stays on the current Home Assistant origin", () => {
  const resolved = new URL(SETUP_URL, "https://ha.example.test");
  assert.equal(resolved.origin, "https://ha.example.test");
  assert.equal(resolved.pathname, "/_my_redirect/config_flow_start");
  assert.equal(resolved.searchParams.get("domain"), "hikconnect_cloud_relay");
  assert.equal(resolved.port, "");
});

test("only actual cloud camera entities appear", () => {
  assert.deepEqual(cloudCameraIds({
    "camera.cloud_one": { attributes: { cloud_provider: "hikconnect_cloud_relay" } },
    "camera.phone": { attributes: {} },
    "sensor.cloud": { attributes: { cloud_provider: "hikconnect_cloud_relay" } },
    "camera.invalid<script>": { attributes: { cloud_provider: "hikconnect_cloud_relay" } }
  }), ["camera.cloud_one"]);
});

test("no invented cameras before account setup", () => {
  assert.deepEqual(cloudCameraIds({}), []);
});

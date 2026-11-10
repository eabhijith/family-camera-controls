import assert from "node:assert/strict";
import test from "node:test";
import { cloudCameraIds } from "../www/hik-cloud-grid-card.js";

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

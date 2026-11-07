import test from "node:test";
import assert from "node:assert/strict";
import { cropRegion } from "../www/view-geometry.mjs";

test("both views preserve the full image", () => {
  assert.deepEqual(cropRegion(1920,2160), {x:0,y:0,width:1920,height:2160});
});
test("upper/lower crops partition every row", () => {
  const upper=cropRegion(800,449,"upper"), lower=cropRegion(800,449,"lower");
  assert.equal(upper.height,lower.y);
  assert.equal(upper.height+lower.height,449);
});
test("custom split remains inside the image", () => {
  for (const split of [.05,.5,.95]) {
    const lower=cropRegion(100,3,"lower",split);
    assert.ok(lower.height>=1);
    assert.equal(lower.y+lower.height,3);
  }
});
test("invalid views/dimensions/splits are rejected", () => {
  assert.throws(()=>cropRegion(0,100));
  assert.throws(()=>cropRegion(100,1));
  assert.throws(()=>cropRegion(100,100,"sideways"));
  assert.throws(()=>cropRegion(100,100,"both",NaN));
});

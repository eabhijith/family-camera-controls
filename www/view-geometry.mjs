/** Display-only crop geometry; this never sends PTZ commands. */
export function cropRegion(width, height, view = "both", split = 0.5) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 2) {
    throw new Error("Invalid image dimensions");
  }
  if (!Number.isFinite(split) || split < 0.05 || split > 0.95) throw new Error("Invalid split");
  const boundary = Math.max(1, Math.min(height - 1, Math.round(height * split)));
  if (view === "both") return { x: 0, y: 0, width, height };
  if (view === "upper") return { x: 0, y: 0, width, height: boundary };
  if (view === "lower") return { x: 0, y: boundary, width, height: height - boundary };
  throw new Error("Unknown view");
}

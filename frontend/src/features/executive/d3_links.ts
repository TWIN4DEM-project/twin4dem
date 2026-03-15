import type * as d3 from "d3";
import type { MinisterLink, MinisterNode } from "@/features/executive/types.ts";

export function computeCurvedLinkPath(
  d: MinisterLink,
  radiusScale: (v: number) => number,
  radiusSelector: (n: MinisterNode) => number,
) {
  if (typeof d.source !== "object" || typeof d.target !== "object") {
    return "";
  }

  const sr = radiusScale(radiusSelector(d.source));
  const tr = radiusScale(radiusSelector(d.target));

  const sx = d.source.x || 0;
  const sy = d.source.y || 0;
  const tx = d.target.x || 0;
  const ty = d.target.y || 0;

  const dx = tx - sx;
  const dy = ty - sy;
  const delta = Math.sqrt(dx * dx + dy * dy);

  const a1 = sx + (sr * dx) / delta;
  const b1 = sy + (sr * dy) / delta;

  const a2 = tx - (tr * dx) / delta;
  const b2 = ty - (tr * dy) / delta;

  return `M${a1},${b1}A${delta},${delta} 0 0,1 ${a2},${b2}`;
}

export function createArrowMarker(
  svg: d3.Selection<SVGSVGElement, unknown, null, unknown>,
) {
  svg
    .append("defs")
    .append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -5 20 20")
    .attr("refX", 20)
    .attr("refY", 0)
    .attr("markerWidth", 5)
    .attr("markerHeight", 5)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L20,0L0,5");
}

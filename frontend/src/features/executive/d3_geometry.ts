import * as d3 from "d3";
import type { MinisterNode } from "@/features/executive/types.ts";

export function computeNodeBounds(nodes: MinisterNode[]) {
  return {
    minX: d3.min(nodes, (d) => d.x || 0) || 0,
    maxX: d3.max(nodes, (d) => d.x || 0) || 0,
    minY: d3.min(nodes, (d) => d.y || 0) || 0,
    maxY: d3.max(nodes, (d) => d.y || 0) || 0,
  };
}

export function computeFitTransform(
  bounds: ReturnType<typeof computeNodeBounds>,
  width: number,
  height: number,
  padding = 20,
) {
  const graphWidth = bounds.maxX - bounds.minX;
  const graphHeight = bounds.maxY - bounds.minY;

  const scale = Math.min(
    (width - padding * 2) / graphWidth,
    (height - padding * 2) / graphHeight,
  );

  const tx = width / 2 - scale * (bounds.minX + graphWidth / 2);
  const ty = height / 2 - scale * (bounds.minY + graphHeight / 2);

  return { scale, tx, ty };
}

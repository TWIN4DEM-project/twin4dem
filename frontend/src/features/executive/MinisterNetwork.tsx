import { type RefObject, useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { Minister } from "@/types/simulation.ts";
import "./MinisterNetwork.scss";
import type { MinisterLink, MinisterNode } from "@/features/executive/types.ts";
import {
  computeCurvedLinkPath,
  createArrowMarker,
} from "@/features/executive/d3_links.ts";
import {
  computeFitTransform,
  computeNodeBounds,
} from "@/features/executive/d3_geometry.ts";

export interface MinisterVote {
  minister: Minister;
  vote: boolean | null;
}

interface MinisterNetworkProps {
  ministerVotes: MinisterVote[];
  width?: number;
  height?: number;
  nodeDistance?: number;
  minNodeRadius?: number;
  maxNodeRadius?: number;
  minEdgeThickness?: number;
  maxEdgeThickness?: number;
}

function initSvg(svgRef: RefObject<SVGSVGElement | null>) {
  if (!svgRef.current) return;

  const svg = d3.select(svgRef.current);
  svg.selectAll("*").remove();
  return svg;
}

function createSimulation(
  svg: d3.Selection<SVGSVGElement, unknown, null, unknown>,
  nodes: d3.Selection<SVGCircleElement, MinisterNode, SVGGElement, unknown>,
  edges: d3.Selection<SVGPathElement, MinisterLink, SVGGElement, unknown>,
  nodeDistance: number,
  width: number,
  height: number,
) {
  createArrowMarker(svg);
  return d3
    .forceSimulation<MinisterNode>(nodes.data())
    .force(
      "link",
      d3
        .forceLink<MinisterNode, MinisterLink>(edges.data())
        .id((d) => d.id)
        .distance(nodeDistance),
    )
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .alpha(1)
    .alphaDecay(0.1)
    .alphaMin(0.05);
}

function createEdges(
  parentNode: d3.Selection<SVGGElement, unknown, null, undefined>,
  ministers: Minister[],
  strokeScale: d3.ScaleLinear<number, number>,
) {
  const ministerLinks: MinisterLink[] = ministers.flatMap((m) =>
    m.neighboursOut.map((targetId) => ({
      source: m.id,
      target: targetId,
      influence: m.influence,
    })),
  );
  return parentNode
    .append("g")
    .selectAll("path")
    .data(ministerLinks)
    .enter()
    .append("path")
    .attr("fill", "none")
    .attr("stroke-width", (d) => strokeScale(d.influence))
    .attr("marker-end", "url(#arrow)");
}

function createNodes(
  parentNode: d3.Selection<SVGGElement, unknown, null, undefined>,
  ministerVotes: MinisterVote[],
  radiusScale: d3.ScaleLinear<number, number>,
  radiusSelector: (n: MinisterNode) => number,
) {
  const ministerNodes: MinisterNode[] = ministerVotes.map(
    ({ minister, vote }) => ({
      ...minister,
      vote: vote ? "approve" : vote === false ? "reject" : "abstain",
    }),
  );
  const nodes = parentNode
    .append("g")
    .selectAll("circle")
    .data(ministerNodes)
    .enter()
    .append("circle")
    .attr("r", (d) => radiusScale(radiusSelector(d)))
    .attr("class", (d) => `node node--${d.vote}`);
  const labels = parentNode
    .append("g")
    .selectAll("text")
    .data(ministerNodes)
    .enter()
    .append("text")
    .text((d) => `${d.label} (${d.partyLabel})`)
    .attr("x", (d) => d.x!)
    .attr("y", (d) => d.y!)
    .attr("text-anchor", "middle")
    .attr("dy", (d) => radiusScale(radiusSelector(d)) + 6);
  return { nodes, labels };
}

export function MinisterNetwork({
  ministerVotes,
  width = 320,
  height = 320,
  nodeDistance = 100,
  minNodeRadius = 3,
  maxNodeRadius = 8,
  minEdgeThickness = 0.25,
  maxEdgeThickness = 1.25,
}: MinisterNetworkProps) {
  const ministers = useMemo(
    () => ministerVotes.map((x) => x.minister),
    [ministerVotes],
  );
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = initSvg(svgRef);
    if (!svg || ministerVotes.length == 0) return;

    const root = svg.append("g");
    const radiusScale = d3
      .scaleLinear()
      .domain(
        d3.extent(ministers, (d) => d.neighboursOut.length) as [number, number],
      )
      .range([minNodeRadius, maxNodeRadius]);
    const strokeScale = d3
      .scaleLinear()
      .domain(d3.extent(ministers, (d) => d.influence) as [number, number])
      .range([minEdgeThickness, maxEdgeThickness]);
    const radiusSelector = (ministerNode: MinisterNode) =>
      ministerNode.neighboursOut.length * ministerNode.influence;
    const { nodes, labels } = createNodes(
      root,
      ministerVotes,
      radiusScale,
      radiusSelector,
    );
    const edges = createEdges(root, ministers, strokeScale);

    const simulation = createSimulation(
      svg,
      nodes,
      edges,
      nodeDistance,
      width,
      height,
    );
    simulation.on("tick", () => {
      edges.attr("d", (d) =>
        computeCurvedLinkPath(d, radiusScale, radiusSelector),
      );
      nodes.attr("cx", (d) => d.x!).attr("cy", (d) => d.y!);
      labels.attr("x", (d) => d.x!).attr("y", (d) => d.y!);
    });
    simulation.on("end", () => {
      const labelNodes = labels.nodes() as SVGTextElement[];
      const labelBounds = labelNodes.map((el) => el.getBBox());
      const bounds = computeNodeBounds(nodes.data());
      labelBounds.forEach((b) => {
        bounds.minX = Math.min(bounds.minX, b.x);
        bounds.minY = Math.min(bounds.minY, b.y);
        bounds.maxX = Math.max(bounds.maxX, b.x + b.width);
        bounds.maxY = Math.max(bounds.maxY, b.y + b.height);
      });
      const transform = computeFitTransform(bounds, width, height, 20);
      root.attr(
        "transform",
        `translate(${transform.tx},${transform.ty}) scale(${transform.scale})`,
      );
    });

    return () => {
      simulation.stop();
    };
  }, [
    ministers,
    width,
    height,
    nodeDistance,
    minEdgeThickness,
    maxEdgeThickness,
    minNodeRadius,
    maxNodeRadius,
  ]);

  return (
    <div className="ministerNetworkContainer">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
}

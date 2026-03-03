import { useEffect, useRef } from "react";
import * as Plot from "@observablehq/plot";
import "../common/NodeColors.scss";
import "./Legend.scss";
import {
  colorscheme,
  max_node_radius,
  min_node_radius,
} from "@/features/common/vars.ts";

interface LegendProps {
  parties: string[];
  min_influence_radius: number;
  max_influence_radius: number;
  width?: number;
  height?: number;
}

export function Legend({
  parties,
  min_influence_radius = min_node_radius,
  max_influence_radius = max_node_radius,
  width = 600,
  height = 120,
}: LegendProps) {
  const svgRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!svgRef) return;

    const circle_options: Plot.DotOptions = {
      dy: -10,
      frameAnchor: "right",
    };

    const text_options: Plot.TextOptions = {
      ...circle_options,
      fill: "#000",
      textAnchor: "middle",
    };

    // Plot radius legend
    const middle_influence_radius =
      (min_influence_radius + max_influence_radius) / 2;
    const radii = [
      min_influence_radius,
      middle_influence_radius,
      max_influence_radius,
    ];
    const radii_labels = [0, 0.5, 1];
    const influence_legend_length = 150;
    const offsets: number[] = [];
    const radius_legend = Plot.marks([
      radii.map((radius, index) => {
        const dx =
          (index - radii.length) * (influence_legend_length / radii.length);
        offsets.push(dx);
        return [
          Plot.circle([radius], {
            ...circle_options,
            r: radius,
            dx,
            className: "node node--abstain",
          }),
          Plot.text([radii_labels[index]], {
            ...text_options,
            dx,
          }),
        ];
      }),
      Plot.text(["Influence"], {
        ...text_options,
        fill: "#fff",
        dy: max_influence_radius + 10,
        dx: (offsets[0] + offsets[offsets.length - 1]) / 2,
      }),
    ]);
    const color_legend_length = 180;
    const color_legend_item_length = color_legend_length / 3;
    const vote_circle_radius = 25;
    const color_legend_offset =
      influence_legend_length + vote_circle_radius + 50;

    const vote_color_legend = Plot.marks([
      Plot.circle([2], {
        ...circle_options,
        dx: -(color_legend_offset + color_legend_item_length * 2),
        r: vote_circle_radius,
        className: "node node--approve",
      }),
      Plot.text(["For"], {
        ...text_options,
        dx: -(color_legend_offset + color_legend_item_length * 2),
      }),
      Plot.circle([1], {
        ...circle_options,
        dx: -(color_legend_offset + color_legend_item_length),
        r: vote_circle_radius,
        className: "node node--reject",
      }),
      Plot.text(["Against"], {
        ...text_options,
        dx: -(color_legend_offset + color_legend_item_length),
      }),
      Plot.circle([0], {
        ...circle_options,
        dx: -color_legend_offset,
        r: vote_circle_radius,
        className: "node node--abstain",
      }),
      Plot.text(["Abstain"], {
        ...text_options,
        dx: -color_legend_offset,
      }),
      Plot.text(["Voting choice"], {
        ...text_options,
        dx: -(color_legend_offset + color_legend_item_length),
        dy: vote_circle_radius + 10,
        fontSize: 15,
        fill: "#fff",
      }),
    ]);

    const party_legend_item_length = 70;
    const party_legend_length = parties.length * party_legend_item_length;
    const party_circle_radius = 20;
    const party_color = Plot.scale({
      color: { scheme: colorscheme, domain: parties },
    });

    const party_legend = Plot.marks([
      parties.map((party, index) => {
        const dx =
          index * (party_legend_length / parties.length) +
          party_circle_radius +
          10;
        return [
          Plot.circle([party], {
            ...circle_options,
            dx,
            fill: party_color.apply(party),
            frameAnchor: "left",
            r: party_circle_radius,
          }),
          Plot.text([party], {
            ...text_options,
            dx,
            dy: party_circle_radius + 5,
            fill: "#fff",
            frameAnchor: "left",
          }),
        ];
      }),
      Plot.text(["Parties"], {
        ...text_options,
        dx: (party_legend_length - party_circle_radius) / 2,
        dy: party_circle_radius + 25,
        fontSize: 15,
        fill: "#fff",
        frameAnchor: "left",
        textAnchor: "middle",
      }),
    ]);

    const plot = Plot.plot({
      width,
      height,
      marks: [radius_legend, vote_color_legend, party_legend],
    });

    svgRef.current?.append(plot);
    return () => plot.remove();
  }, [parties, width, height, max_influence_radius, min_influence_radius]);

  return <div ref={svgRef} id="legend" />;
}

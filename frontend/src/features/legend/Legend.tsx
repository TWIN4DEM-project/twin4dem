import * as Plot from "@observablehq/plot";
import { useEffect, useRef } from "react";
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
  height?: number;
  main_label_offset: number;
}

export function Legend({
  parties,
  min_influence_radius = min_node_radius,
  max_influence_radius = max_node_radius,
  height = 150,
  main_label_offset = 50,
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
    const middle_influence_radius = (min_influence_radius + max_influence_radius) / 2;
    const radii = [min_influence_radius, middle_influence_radius, max_influence_radius];
    const radii_labels = [0, 0.5, 1];
    const influence_legend_width = 150;
    const offsets: number[] = [];
    const radius_legend = Plot.marks([
      radii.map((radius, index) => {
        const dx = (index - radii.length) * (influence_legend_width / radii.length);
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
        fontSize: 15,
        dy: -main_label_offset,
        dx: (offsets[0] + offsets[offsets.length - 1]) / 2,
      }),
    ]);
    const vote_legend_width = 180;
    const vote_legend_item_width = vote_legend_width / 3;
    const vote_circle_radius = 25;
    const color_legend_offset = influence_legend_width + vote_circle_radius + 50;

    const vote_color_legend = Plot.marks([
      Plot.circle([2], {
        ...circle_options,
        dx: -(color_legend_offset + vote_legend_item_width * 2),
        r: vote_circle_radius,
        className: "node node--approve",
      }),
      Plot.text(["For"], {
        ...text_options,
        dx: -(color_legend_offset + vote_legend_item_width * 2),
      }),
      Plot.circle([1], {
        ...circle_options,
        dx: -(color_legend_offset + vote_legend_item_width),
        r: vote_circle_radius,
        className: "node node--reject",
      }),
      Plot.text(["Against"], {
        ...text_options,
        dx: -(color_legend_offset + vote_legend_item_width),
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
        dx: -(color_legend_offset + vote_legend_item_width),
        dy: -main_label_offset,
        fontSize: 15,
        fill: "#fff",
      }),
    ]);

    const party_legend_item_width = 100;
    const party_legend_width = parties.length * party_legend_item_width;
    const party_circle_radius = 20;
    const party_color = Plot.scale({
      color: { scheme: colorscheme, domain: parties },
    });

    const party_legend = Plot.marks([
      parties.map((party, index) => {
        const dx = index * party_legend_item_width + party_circle_radius + 10;
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
            dy: party_circle_radius + 20,
            fill: "#fff",
            frameAnchor: "left",
            lineWidth: 10,
          }),
        ];
      }),
      Plot.text(["Parties"], {
        ...text_options,
        dx: party_legend_width / 2 - party_circle_radius,
        dy: -main_label_offset,
        fontSize: 15,
        fill: "#fff",
        frameAnchor: "left",
        textAnchor: "middle",
      }),
    ]);

    const plot_width =
      influence_legend_width + vote_legend_width + party_legend_width + 50;
    const plot = Plot.plot({
      width: plot_width,
      height,
      marks: [radius_legend, vote_color_legend, party_legend],
    });

    svgRef.current?.append(plot);
    return () => plot.remove();
  }, [parties, height, max_influence_radius, min_influence_radius, main_label_offset]);

  return <div ref={svgRef} id="legend" />;
}

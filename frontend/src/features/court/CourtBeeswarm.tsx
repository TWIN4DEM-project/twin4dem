import * as Plot from "@observablehq/plot";
import { useEffect, useMemo, useRef } from "react";
import { displayVote } from "@/features/common/utils";
import { headingSummaryResult, tallyVotes } from "@/features/common/utils.ts";
import { VoteTallyFormat } from "@/features/common/VoteTallyFormat.tsx";
import {
  colorscheme,
  max_node_radius,
  min_node_radius,
  vote_categories,
} from "@/features/common/vars.ts";
import type { Judge } from "@/types/simulation.ts";

export interface JudgeVote {
  judge: Judge;
  vote: boolean | null;
}

interface CourtNetworkProps {
  courtVotes: JudgeVote[];
  isActive: boolean;
  step: number;
}

export function CourtBeeswarm({ courtVotes, isActive, step }: CourtNetworkProps) {
  const svgRef = useRef<HTMLDivElement | null>(null);
  const courtStep = useMemo(() => step, [step]);

  useEffect(() => {
    if (!svgRef || courtVotes.length === 0) return;

    const plot = Plot.plot({
      color: { scheme: colorscheme },
      marginLeft: 200,
      y: { grid: true },
      r: { range: [min_node_radius, max_node_radius] },
      fx: { domain: vote_categories },
      marks: [
        Plot.dot(
          courtVotes,
          Plot.dodgeX("middle", {
            fx: (v) => displayVote(v.vote),
            fill: (v) => v.judge.partyLabel,
            stroke: (v) => (v.judge.isPresident ? "#FFF" : "none"),
            strokeWidth: (v) => (v.judge.isPresident ? "2px" : "0"),
            strokeDasharray: "2 2",
            y: (v) => v.judge.label,
            r: (v) => v.judge.influence,
            tip: {
              title: (v) => v.judge.label,
              fill: "black",
              fx: (v) => displayVote(v.vote),
              y: (v) => v.judge.label,
              format: {
                strokeWidth: false,
              },
            },
          }),
        ),
        Plot.axisY({
          facetAnchor: "left",
        }),
      ],
    });

    svgRef.current?.append(plot);
    return () => plot.remove();
  }, [courtVotes]);

  const votes = tallyVotes(courtVotes);

  return (
    <div
      className={`judicialContainer ${isActive ? "active-branch" : "inactive-branch"}`}
    >
      <figure>
        <h2>Court{headingSummaryResult(votes, isActive)}</h2>
        <div ref={svgRef} id="court-visualisation" />
        {isActive ? (
          <>
            <p>
              At step <b>{courtStep}</b>, the Court decides on the Government's
              proposal.
            </p>
            <VoteTallyFormat votes={votes} />
          </>
        ) : null}
      </figure>
    </div>
  );
}

import * as Plot from "@observablehq/plot";
import { useEffect, useMemo, useRef } from "react";
import {
  displayVote,
  headingSummaryResult,
  tallyVotes,
} from "@/features/common/utils.ts";
import { VoteTallyFormat } from "@/features/common/VoteTallyFormat.tsx";
import {
  colorscheme,
  min_node_radius,
  vote_categories,
} from "@/features/common/vars.ts";
import type { MemberOfParliament } from "@/types/simulation.ts";

export interface MemberVote {
  mp: MemberOfParliament;
  vote: boolean | null;
}

interface ParliamentBeeswarmProps {
  memberVotes: MemberVote[];
  isActive: boolean;
  step: number;
}

export function ParliamentBeeswarm({
  memberVotes,
  isActive,
  step,
}: ParliamentBeeswarmProps) {
  const svgRef = useRef<HTMLDivElement | null>(null);
  const parliamentStep = useMemo(() => step, [step]);

  useEffect(() => {
    if (!svgRef || memberVotes.length === 0) return;

    const mpIds = memberVotes.map((m) => m.mp.id);
    const minId = Math.min(...mpIds);
    const maxId = Math.max(...mpIds);

    const plot = Plot.plot({
      fx: { domain: vote_categories },
      y: { domain: [minId, maxId] },
      color: { scheme: colorscheme },
      height: 300,
      marks: [
        Plot.dot(
          memberVotes,
          Plot.dodgeX("middle", {
            fx: (v) => displayVote(v.vote),
            fill: (v) => v.mp.partyLabel,
            y: (v) => v.mp.id,
            stroke: (v) => (v.mp.isHead ? "#FFF" : "none"),
            strokeWidth: (v) => (v.mp.isHead ? "2px" : "0"),
            strokeDasharray: "2 2",
            r: min_node_radius,
            channels: {
              label: (v) => v.mp.label,
            },
            tip: {
              title: (v) => v.mp.label,
              fill: "black",
              fx: (v) => displayVote(v.vote),
              format: {
                strokeWidth: false,
                label: true,
              },
            },
          }),
        ),
      ],
    });

    svgRef.current?.append(plot);
    return () => plot.remove();
  }, [memberVotes]);

  const votes = tallyVotes(memberVotes);

  return (
    <div
      className={`legislativeContainer ${isActive ? "active-branch" : "inactive-branch"}`}
    >
      <figure>
        <h2>Parliament{headingSummaryResult(votes, isActive)}</h2>
        <div ref={svgRef} id="parliament-visualisation" />
        {isActive ? (
          <>
            <p>
              At step <b>{parliamentStep}</b>, the Parliament votes on the Government's
              proposal.
            </p>
            <VoteTallyFormat votes={votes} />
          </>
        ) : null}
      </figure>
    </div>
  );
}

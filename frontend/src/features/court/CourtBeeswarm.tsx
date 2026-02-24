import {useEffect, useMemo, useRef} from "react";
import * as Plot from "@observablehq/plot";
import {displayVote} from "@/features/legislative/ParliamentBeeswarm.tsx";
import {colorscheme, max_node_radius, min_node_radius, vote_categories} from "@/features/common/vars.ts";
import {type AgentVote, headingSummaryResult, tallyVotes} from "@/features/common/utils.ts";
import {VoteTallyFormat} from "@/features/common/VoteTallyFormat.tsx";
import type {Judge} from "@/types/simulation.ts";

interface CourtNetworkProps {
    courtVotes: AgentVote<Judge>[],
    isActive: boolean,
    step: number
}

function drawPlot(votes: AgentVote<Judge>[]) {
    return Plot.plot({
        color: {scheme: colorscheme},
        y: {grid: true},
        r: {range: [min_node_radius, max_node_radius]},
        fx: {domain: vote_categories},
        marks: [
            Plot.dot(votes,
                Plot.dodgeX("middle", {
                    fx: v => displayVote(v.vote),
                    fill: v => v.agent.partyLabel,
                    stroke: v => v.agent.isPresident ? "#FFF" : "none",
                    strokeWidth: v => v.agent.isPresident ? "2px" : "0",
                    strokeDasharray: "2 2",
                    y: v => v.agent.label,
                    r: v => v.agent.influence,
                    tip: {
                        title: v => v.agent.label,
                        fill: "black",
                        fx: v => displayVote(v.vote),
                        y: v => v.agent.label,
                        format: {
                            strokeWidth: false,
                        }
                    }
                })),
        ]
    });
}

export function CourtBeeswarm({courtVotes, isActive, step}: CourtNetworkProps) {
    const svgRef = useRef<HTMLDivElement | null>(null);
    const courtStep = useMemo(() => step, [courtVotes]);

    useEffect(() => {
        if (!svgRef || courtVotes.length == 0) return;

        const plot = drawPlot(courtVotes);
        svgRef.current?.append(plot);
        return () =>  plot.remove();
    }, [courtVotes]);

    const votes = tallyVotes(courtVotes);

    return (
        <div className={`judicialContainer ${isActive ? "active-branch" : "inactive-branch"}`}>
            <figure>
                <h2>Court{headingSummaryResult(votes, isActive)}</h2>
                <div ref={svgRef} id="court-visualisation"/>
                {isActive &&
                    <>
                        <p>At step <b>{courtStep}</b>, the Court decides on the Government's proposal.</p>
                        <VoteTallyFormat votes={votes}/>
                    </>
                }
            </figure>
        </div>
    );
}
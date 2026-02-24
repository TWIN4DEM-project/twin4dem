import type {MemberOfParliament} from "@/types/simulation.ts";
import {useEffect, useMemo, useRef} from "react";
import * as Plot from "@observablehq/plot";
import {colorscheme, min_node_radius, vote_categories} from "@/features/common/vars.ts";
import {type AgentVote, headingSummaryResult, tallyVotes} from "@/features/common/utils.ts";
import {VoteTallyFormat} from "@/features/common/VoteTallyFormat.tsx";

interface ParliamentBeeswarmProps {
    memberVotes: AgentVote<MemberOfParliament>[],
    isActive: boolean,
    step: number,
}

function drawPlot(votes: AgentVote<MemberOfParliament>[]) {
    const mpIds = votes.map(m => m.agent.id);
    const minId = Math.min(...mpIds);
    const maxId = Math.max(...mpIds);

    return Plot.plot({
        fx: {domain: vote_categories},
        y: {domain: [minId, maxId]},
        color: {scheme: colorscheme},
        height: 300,
        marks: [
            Plot.dot(votes, Plot.dodgeX("middle", {
                fx: v => displayVote(v.vote),
                fill: v => v.agent.partyLabel,
                y: v => v.agent.id,
                stroke: v => v.agent.isHead ? "#FFF" : "none",
                strokeWidth: v => v.agent.isHead ? "2px" : "0",
                strokeDasharray: "2 2",
                r: min_node_radius,
                channels: {
                    label: v => v.agent.label,
                },
                tip: {
                    title: v => v.agent.label,
                    fill: "black",
                    fx: v => displayVote(v.vote),
                    format: {
                        strokeWidth: false,
                        label: true,
                    }
                }
            })),
        ]
    });
}

export function displayVote(vote: boolean | null) {
    if (vote === null) {
        return "Abstain";
    }
    return vote ? "For" : "Against";
}

export function ParliamentBeeswarm(
    {
        memberVotes,
        isActive,
        step
    }: ParliamentBeeswarmProps)
{
    const svgRef = useRef<HTMLDivElement | null>(null);
    const parliamentStep = useMemo(() => step, [memberVotes]);

    useEffect(() => {
        if (!svgRef || memberVotes.length == 0) return;
        const plot = drawPlot(memberVotes);
        svgRef.current?.append(plot);
        return () =>  plot.remove();
    }, [memberVotes]);

    const votes = tallyVotes(memberVotes);

    return (
        <div className={`legislativeContainer ${isActive ? "active-branch" : "inactive-branch"}`}>
            <figure>
                <h2>Parliament{headingSummaryResult(votes, isActive)}</h2>
                <div ref={svgRef} id="parliament-visualisation"/>
                {isActive &&
                    <>
                        <p>At step <b>{parliamentStep}</b>, the Parliament votes on the Government's proposal.</p>
                        <VoteTallyFormat votes={votes}/>
                    </>
                }
            </figure>
        </div>
    );
}
import {MinisterNetwork} from "@/features/executive/MinisterNetwork.tsx";
import {ParliamentBeeswarm} from "@/features/legislative/ParliamentBeeswarm.tsx";
import {CourtBeeswarm} from "@/features/court/CourtBeeswarm.tsx";
import "./SubmodelContainer.scss";
import {Legend} from "@/features/legend/Legend.tsx";
import type {Votes} from "@/features/simulations/SimulationDetails.tsx";

interface SubmodelContainerProps {
    parties: string[],
    votes: Votes,
    path: "legislative act" | "decree" | undefined,
    step: number,
  aggrandizementPassed: null | boolean,
}

export function SubmodelContainer({parties, votes, path, step, aggrandizementPassed}: SubmodelContainerProps) {
  console.log(votes);


    return (
      <div>
        <div className="simulationStep">
          <div className="votingOutcome">
            <div>
              Path: <strong>{path}</strong>
            </div>
            <div>
              Voting Outcome:{" "}
              <strong>
                {aggrandizementPassed === null
                  ? "-"
                  : `Aggrandisement ${aggrandizementPassed ? "Passed" : "Failed"}`}
              </strong>
            </div>
          </div>
          <Legend
            parties={parties}
            min_influence_radius={10}
            max_influence_radius={20}
          />
          <div className="submodelContainer">
            <MinisterNetwork ministerVotes={votes.cabinet} isActive={path !== undefined} path={path} step={step}/>
            <div className="rightPanel">
                <ParliamentBeeswarm memberVotes={votes.parliament} isActive={path === "legislative act"} step={step}/>
                <CourtBeeswarm courtVotes={votes.court} isActive={path === "decree"} step={step}/>
            </div>
          </div>
        </div>
      </div>
  );
}

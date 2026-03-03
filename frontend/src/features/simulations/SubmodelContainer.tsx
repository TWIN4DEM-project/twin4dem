import {
  MinisterNetwork,
  type MinisterVote,
} from "@/features/executive/MinisterNetwork.tsx";
import {
  type MemberVote,
  ParliamentBeeswarm,
} from "@/features/legislative/ParliamentBeeswarm.tsx";
import {
  CourtBeeswarm,
  type JudgeVote,
} from "@/features/court/CourtBeeswarm.tsx";
import "./SubmodelContainer.scss";
import { Legend } from "@/features/legend/Legend.tsx";

interface SubmodelContainerProps {
  parties: string[];
  ministerVotes: MinisterVote[];
  mpVotes: MemberVote[];
  courtVotes: JudgeVote[];
  path: "legislative act" | "decree" | undefined;
  aggrandizementPassed: null | boolean;
  step: number;
}

export function SubmodelContainer({
  parties,
  ministerVotes,
  mpVotes,
  courtVotes,
  path,
  aggrandizementPassed,
  step,
}: SubmodelContainerProps) {
  return (
    <div>
      <div className="simulationStep">
        <div className="votingOutcome">
          <div>
            Path: <strong>{path ?? "-"}</strong>
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
          <MinisterNetwork ministerVotes={ministerVotes} isActive={path !== undefined} path={path} step={step}/>
          <div className="rightPanel">
              <ParliamentBeeswarm memberVotes={mpVotes} isActive={path === "legislative act"} step={step}/>
              <CourtBeeswarm courtVotes={courtVotes} isActive={path === "decree"} step={step}/>
          </div>
        </div>
      </div>
    </div>
  );
}

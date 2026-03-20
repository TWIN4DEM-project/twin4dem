import { useState } from "react";

import type { JudgeVote } from "@/features/court/CourtBeeswarm.tsx";
import type { MinisterVote } from "@/features/executive/MinisterNetwork.tsx";
import { SimulationHistoryPlotContainer } from "@/features/history/SimulationHistoryPlotContainer.tsx";
import type { MemberVote } from "@/features/legislative/ParliamentBeeswarm.tsx";
import { SubmodelContainer } from "@/features/simulations/SubmodelContainer.tsx";
import "./SimulationTabbedContainer.scss";
import { useSimulationLog } from "@/features/history/hooks.ts";
import type { SimulationLog } from "@/types/simulation_log.ts";

type SimulationTabbedContainerProps = {
  parties: string[];
  ministerVotes: MinisterVote[];
  mpVotes: MemberVote[];
  courtVotes: JudgeVote[];
  path: "legislative act" | "decree" | undefined;
  aggrandizementPassed: null | boolean;
  stepNo: number;
  simulationId: number | undefined;
};

type TabType = "real-time" | "log";

type TabProps = {
  label: string;
  isActive: boolean;
  onClick: () => void;
};

const Tab = ({ label, isActive, onClick }: TabProps) => {
  return (
    <button
      type="button"
      className={`button ${isActive ? "button--outline" : "button--ghost"}`}
      onClick={onClick}
    >
      <h4>{label}</h4>
    </button>
  );
};

export default function SimulationTabbedContainer({
  parties,
  ministerVotes,
  mpVotes,
  courtVotes,
  path,
  aggrandizementPassed,
  stepNo,
  simulationId,
}: SimulationTabbedContainerProps) {
  const [currentTab, setCurrentTab] = useState<TabType>("real-time");
  const simulationLog: SimulationLog = useSimulationLog(
    simulationId,
    stepNo,
    currentTab === "log",
  );

  return (
    <>
      <div className="tabRow">
        <Tab
          label="Real Time"
          isActive={currentTab === "real-time"}
          onClick={() => setCurrentTab("real-time")}
        />
        <Tab
          label={"Log"}
          isActive={currentTab === "log"}
          onClick={() => setCurrentTab("log")}
        />
      </div>
      {currentTab === "real-time" && (
        <SubmodelContainer
          parties={parties}
          ministerVotes={ministerVotes}
          mpVotes={mpVotes}
          courtVotes={courtVotes}
          path={path}
          aggrandizementPassed={aggrandizementPassed}
          step={stepNo}
        />
      )}
      {currentTab === "log" && (
        <SimulationHistoryPlotContainer simulationLog={simulationLog} />
      )}
    </>
  );
}

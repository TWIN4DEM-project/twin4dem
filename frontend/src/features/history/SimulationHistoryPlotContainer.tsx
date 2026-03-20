import BranchVotePlot from "@/features/history/BranchVotePlot.tsx";
import { CumulativeSuccessfulAttemptPlot } from "@/features/history/CumulativeSuccessfulAttemptPlot.tsx";
import "./SimulationHistoryPlotContainer.scss";
import type { SimulationLog } from "@/types/simulation_log.ts";

type SimulationLogPlotContainerProps = {
  simulationLog: SimulationLog;
};

export function SimulationHistoryPlotContainer({
  simulationLog,
}: SimulationLogPlotContainerProps) {
  return (
    <div className="simulationInfoCard">
      <div className="infoCardHeader">
        <h1>Voting trends over time</h1>
      </div>
      <CumulativeSuccessfulAttemptPlot log={simulationLog} />
      <BranchVotePlot log={simulationLog} type={"executive"} title="Government votes" />
      <BranchVotePlot
        log={simulationLog}
        type={"legislative"}
        title="Parliament votes"
      />
      <BranchVotePlot log={simulationLog} type={"judiciary"} title="Court votes" />
    </div>
  );
}

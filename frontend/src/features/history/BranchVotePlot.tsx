import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import type {
  SimulationLog,
  SimulationLogSubmodelType,
} from "@/types/simulation_log.ts";

type BranchVotePlotProps = {
  log: SimulationLog;
  type: SimulationLogSubmodelType;
  title: string;
};

function filterBranchVotes(log: SimulationLog, type: SimulationLogSubmodelType) {
  const results = log.flatMap((step) => {
    return step.submodelResults.map((submodelResult) => {
      return { ...submodelResult, simulationStep: step.stepNo };
    });
  });
  return results.filter((r) => r.submodelType === type);
}

export default function BranchVotePlot({ log, type, title }: BranchVotePlotProps) {
  const branchVotes = filterBranchVotes(log, type);

  return (
    <figure>
      <h2>{title}</h2>
      <BarChart
        style={{
          width: "100%",
          maxHeight: "15rem",
          aspectRatio: 2,
        }}
        margin={{
          top: 20,
          right: 0,
          left: 0,
          bottom: 5,
        }}
        responsive
        data={branchVotes}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="simulationStep"
          niceTicks="snap125"
          interval={0}
          label={{
            value: "Step no.",
            position: "insideBottomLeft",
            offset: -5,
          }}
        />
        <YAxis
          label={{
            value: "Votes",
            position: "insideBottom",
            angle: -90,
          }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "black" }}
          labelFormatter={(step) => `Step: ${step}`}
        />
        <Legend />
        <Bar dataKey="votesFor" stackId="votes" fill="#89D4FF" />
        <Bar dataKey="votesAgainst" stackId="votes" fill="#FE9EC7" />
        <Bar dataKey="abstentions" stackId="votes" fill="#F9F6C4" />
      </BarChart>
    </figure>
  );
}

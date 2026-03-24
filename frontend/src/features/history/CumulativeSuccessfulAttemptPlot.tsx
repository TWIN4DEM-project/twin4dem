import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import type { SimulationLog } from "@/types/simulation_log.ts";

type CumulativePassedAuChartProps = {
  log: SimulationLog;
};

type CumulativeResultStep = {
  totalPassedAttempts: number;
  passedByDecree: number;
  passedByLegislativeProposal: number;
  failedAttempts: number;
  simulationStep: number;
};

function accumulateLogResults(log: SimulationLog): CumulativeResultStep[] {
  log = log.sort((a, b) => a.stepNo - b.stepNo);
  return log.reduce((cumulativeResults: CumulativeResultStep[], currentLog) => {
    let stepResults: CumulativeResultStep;
    if (cumulativeResults.length === 0) {
      stepResults = {
        totalPassedAttempts: 0,
        passedByDecree: 0,
        passedByLegislativeProposal: 0,
        failedAttempts: 0,
        simulationStep: 0,
      };
    } else {
      stepResults = { ...cumulativeResults[cumulativeResults.length - 1] };
    }
    stepResults.simulationStep = currentLog.stepNo;

    if (currentLog.approved) {
      stepResults.totalPassedAttempts += 1;
      if (currentLog.aggrandisementPath === "decree") {
        stepResults.passedByDecree += 1;
      } else if (currentLog.aggrandisementPath === "legislative act") {
        stepResults.passedByLegislativeProposal += 1;
      }
    } else {
      stepResults.failedAttempts += 1;
    }

    cumulativeResults.push(stepResults);
    return cumulativeResults;
  }, []);
}

export function CumulativeSuccessfulAttemptPlot({ log }: CumulativePassedAuChartProps) {
  const successfulAttemptsByStep = accumulateLogResults(log);

  return (
    <figure>
      <h2>Aggrandisement attempts</h2>
      <BarChart
        style={{
          width: "100%",
          maxHeight: "25vh",
          aspectRatio: 2,
        }}
        responsive
        data={successfulAttemptsByStep}
        margin={{
          top: 20,
          right: 0,
          left: 0,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="simulationStep"
          niceTicks="snap125"
          label={{
            value: "Step no.",
            position: "insideBottomLeft",
            offset: -5,
          }}
        />
        <YAxis
          niceTicks="snap125"
          label={{
            value: "Aggrandisement attempts",
            position: "insideLeft",
            angle: -90,
            textAnchor: "middle",
            offset: 10,
          }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "black" }}
          labelFormatter={(step) => `Step: ${step}`}
        />
        <Legend />
        <Bar dataKey="passedByDecree" stackId="attempts" fill="#D8E983" />
        <Bar dataKey="passedByLegislativeProposal" stackId="attempts" fill="#AEB877" />
        <Bar dataKey="failedAttempts" stackId="attempts" fill="#E8F5BD" />
      </BarChart>
    </figure>
  );
}

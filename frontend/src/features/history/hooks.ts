import axios from "axios";
import { useEffect, useState } from "react";
import { type SimulationLog, SimulationLogSchema } from "@/types/simulation_log.ts";

export async function fetchSimulationLog(simulationId: number): Promise<SimulationLog> {
  const resp = await axios.get(`/api/v1/simulation/${simulationId}/log/`, {
    withCredentials: true,
  });
  if (resp.status !== 200) {
    throw Error(`unable to fetch log for simulation ${simulationId}`);
  }
  const simulationLog = await SimulationLogSchema.safeParseAsync(resp.data);
  if (simulationLog.error) {
    throw simulationLog.error;
  }
  return simulationLog.data;
}

function isNewStep(stepNo: number, simulationId: number, simulationLog: SimulationLog) {
  return !simulationLog.some(
    (entry) => entry.stepNo === stepNo && entry.simulationId === simulationId,
  );
}

export function useSimulationLog(
  simulationId: number | undefined,
  stepNo: number,
  shouldFetch: boolean,
) {
  const [simulationLog, setSimulationLog] = useState<SimulationLog>([]);

  useEffect(() => {
    if (!shouldFetch) return;
    if (simulationId === undefined) return;
    if (!isNewStep(stepNo, simulationId, simulationLog)) return;

    const fetch = async () => {
      const simulationLog = await fetchSimulationLog(simulationId);
      setSimulationLog(simulationLog);
    };
    fetch().catch(console.error);
  }, [shouldFetch, simulationId, stepNo, simulationLog]);

  return simulationLog;
}

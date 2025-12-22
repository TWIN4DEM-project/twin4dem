import { useFetch } from "@/hooks/fetch.ts";
import {
  type Simulation,
  type SimulationList,
  SimulationListSchema,
  SimulationSchema,
} from "@/types/simulation";

export function useSimulations() {
  return useFetch<SimulationList>({
    url: "/api/v1/simulation",
    schema: SimulationListSchema,
    initialValue: [],
  });
}

export function useSimulation(simulationId: number | undefined) {
  const url = simulationId ? `/api/v1/simulation/${simulationId}/` : null;
  return useFetch<Simulation>({ url, schema: SimulationSchema });
}

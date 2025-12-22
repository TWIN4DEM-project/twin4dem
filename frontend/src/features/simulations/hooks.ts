import { useFetch } from "@/hooks/fetch.ts";
import {
  type Simulation,
  type SimulationList,
  SimulationListSchema,
  SimulationSchema,
} from "@/types/simulation";
import axios from "axios";

export function useSimulations() {
  return useFetch<SimulationList>({
    url: "/api/v1/simulation",
    method: "GET",
    schema: SimulationListSchema,
    initialValue: [],
  });
}

export function useSimulation(simulationId: number | undefined) {
  const url = simulationId ? `/api/v1/simulation/${simulationId}/` : null;
  return useFetch<Simulation>({ url, schema: SimulationSchema, method: "GET" });
}

export async function createSimulation() {
  const response = await axios.post(
    "/api/v1/simulation/",
    { status: "new" },
    {
      withCredentials: true,
    },
  );
  return await SimulationSchema.parseAsync(response.data);
}

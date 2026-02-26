import { useFetch } from "@/hooks/fetch.ts";
import {
  type Simulation,
  type SimulationList,
  SimulationListSchema,
  SimulationSchema,
} from "@/types/simulation";
import {
  type UserSettings,
  UserSettingsSchema,
  UserSettingsListSchema,
} from "@/types/settings";

import axios from "axios";

export function useSimulations() {
  return useFetch<SimulationList>({
    url: "/api/v1/simulation",
    method: "GET",
    schema: SimulationListSchema,
    initialValue: [],
  });
}

export function useSimulation(simulationId: number | undefined, withHistoricVotes: boolean=false) {
  const urlParams = withHistoricVotes ? `?withHistoricVotes=${withHistoricVotes}` : "";
  const url = simulationId ? (`/api/v1/simulation/${simulationId}/${urlParams}`) : null;
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

export async function fetchSettings(): Promise<UserSettings> {
  let resp = await axios.get("/api/v1/settings/", {withCredentials: true})
  if (resp.status != 200) {
    throw Error("unable to fetch settings list")
  }
  const settingsList = await UserSettingsListSchema.safeParseAsync(resp.data)
  if (settingsList.error) {
    throw settingsList.error
  }
  if (settingsList.data?.length != 1) {
    throw Error("unexpected user settings count")
  }

  resp = await axios.get(`/api/v1/settings/${settingsList.data[0].id}/`, {withCredentials: true})
  if (resp.status != 200) {
    throw Error("unable to fetch settings object")
  }
  const userSettings = await UserSettingsSchema.safeParseAsync(resp.data)
  if (userSettings.error) {
    throw userSettings.error
  }
  return userSettings.data
}

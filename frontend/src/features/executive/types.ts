import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import type { Minister } from "@/types/simulation.ts";

export interface MinisterNode extends Minister, SimulationNodeDatum {
  vote: "approve" | "reject" | "abstain";
}

export interface MinisterLink extends SimulationLinkDatum<MinisterNode> {
  influence: number;
}

import type { Minister } from "@/types/simulation.ts";
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";

export interface MinisterNode extends Minister, SimulationNodeDatum {
  vote: "approve" | "reject" | "abstain";
}

export interface MinisterLink extends SimulationLinkDatum<MinisterNode> {
  influence: number;
}

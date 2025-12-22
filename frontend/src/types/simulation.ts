import { z } from "zod";

const SimulationStatusEnum = z.enum(["new", "running", "complete", "error"]);
export const SimulationListItemSchema = z.object({
  id: z.number(),
  status: SimulationStatusEnum,
  currentStep: z.number(),
  createdAt: z.iso.datetime(),
  updatedAt: z.iso.datetime(),
});
export const SimulationListSchema = z.array(SimulationListItemSchema);

export type SimulationListItem = z.infer<typeof SimulationListItemSchema>;
export type SimulationList = SimulationListItem[];

export const MinisterSchema = z.object({
  id: z.number(),
  label: z.string(),
  isPrimeMinister: z.boolean(),
  partyLabel: z.string(),
  influence: z.number(),
  weights: z.array(z.number()),
  neighboursIn: z.array(z.number()),
  neighboursOut: z.array(z.number()),
});

export const CabinetSchema = z.object({
  id: z.number(),
  label: z.string(),
  governmentProbabilityFor: z.number(),
  legislativeProbability: z.number(),
  ministers: z.array(MinisterSchema),
});

export const SimulationParamSchema = z.object({
  type: z.literal("cabinet"),
  cabinet: CabinetSchema,
});

export const SimulationSchema = z.object({
  id: z.number(),
  createdAt: z.iso.datetime(),
  updatedAt: z.iso.datetime(),
  status: SimulationStatusEnum,
  currentStep: z.number(),
  officeRetentionSensitivity: z.number(),
  socialInfluenceSusceptibility: z.number(),
  params: z.array(SimulationParamSchema),
});

export type Minister = z.infer<typeof MinisterSchema>;
export type Cabinet = z.infer<typeof CabinetSchema>;
export type SimulationParam = z.infer<typeof SimulationParamSchema>;
export type Simulation = z.infer<typeof SimulationSchema>;

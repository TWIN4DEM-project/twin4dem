import { z } from "zod";
import { StepResultSchema } from "./state";

const SimulationStatusEnum = z.enum(["new", "running", "complete", "error"]);
export const SimulationListItemSchema = z.object({
  id: z.number(),
  status: SimulationStatusEnum,
  currentStep: z.number(),
  createdAt: z.iso.datetime(),
  updatedAt: z.iso.datetime(),
  label: z.string(),
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

export const MPSchema = z.object({
  id: z.number(),
  label: z.string(),
  isHead: z.boolean(),
  partyLabel: z.string(),
  partyPosition: z.string(),
  weights: z.array(z.number()),
});

export const ParliamentSchema = z.object({
  id: z.number(),
  label: z.string(),
  majorityProbabilityFor: z.number(),
  oppositionProbabilityFor: z.number(),
  members: z.array(MPSchema),
});

export const JudgeSchema = z.object({
  id: z.number(),
  label: z.string(),
  isPresident: z.boolean(),
  partyLabel: z.string(),
  partyPosition: z.string(),
  influence: z.number(),
  weights: z.array(z.number()),
  neighboursIn: z.array(z.number()),
  neighboursOut: z.array(z.number()),
});

export const CourtSchema = z.object({
  id: z.number(),
  label: z.string(),
  probabilityFor: z.number(),
  judges: z.array(JudgeSchema),
});

export const SimulationParamSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("cabinet"),
    cabinet: CabinetSchema,
  }),
  z.object({
    type: z.literal("parliament"),
    parliament: ParliamentSchema,
  }),
  z.object({
    type: z.literal("court"),
    court: CourtSchema,
  }),
]);

export const SimulationSchema = z.object({
  id: z.number(),
  createdAt: z.iso.datetime(),
  updatedAt: z.iso.datetime(),
  status: SimulationStatusEnum,
  currentStep: z.number(),
  officeRetentionSensitivity: z.number(),
  socialInfluenceSusceptibility: z.number(),
  params: z.array(SimulationParamSchema),
  label: z.string(),
  maxStepCount: z.number().optional(),
  results: z.array(StepResultSchema).optional(),
});

export type Minister = z.infer<typeof MinisterSchema>;
export type Cabinet = z.infer<typeof CabinetSchema>;
export type MemberOfParliament = z.infer<typeof MPSchema>;
export type Parliament = z.infer<typeof ParliamentSchema>;
export type Judge = z.infer<typeof JudgeSchema>;
export type Court = z.infer<typeof CourtSchema>;
export type SimulationParam = z.infer<typeof SimulationParamSchema>;
export type Simulation = z.infer<typeof SimulationSchema>;

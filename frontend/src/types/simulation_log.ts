import { z } from "zod";

export const SimulationLogSubmodelTypeSchema = z.enum([
  "executive",
  "legislative",
  "judiciary",
]);
export const SimulationLogSubmodelResult = z.object({
  submodelType: SimulationLogSubmodelTypeSchema,
  approved: z.boolean(),
  votesFor: z.number(),
  votesAgainst: z.number(),
  abstentions: z.number(),
});

export const SimulationLogStepDecisionTypeEnum = z.enum(["legislative", "judiciary"]);
export const SimulationLogStepAuPath = z.enum(["legislative act", "decree"]);
export const SimulationLogStepSchema = z.object({
  simulationId: z.number(),
  stepNo: z.number(),
  approved: z.boolean(),
  lastDecisionType: SimulationLogStepDecisionTypeEnum,
  aggrandisementPath: SimulationLogStepAuPath,
  submodelResults: SimulationLogSubmodelResult.array(),
});
export const SimulationLogSchema = SimulationLogStepSchema.array();

export type SimulationLog = z.infer<typeof SimulationLogSchema>;
export type SimulationLogSubmodelType = z.infer<typeof SimulationLogSubmodelTypeSchema>;

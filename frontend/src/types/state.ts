import { z } from "zod";

export const CabinetStepResultSchema = z.object({
  type: z.literal("cabinet"),
  approved: z.boolean(),
  path: z.literal(["legislative act", "decree", null]),
  votes: z.record(
    z.string(), // key
    z.union([z.literal(0), z.literal(1), z.null()]), // value
  ),
});
export const VbarStepResultSchema = z.object({
  type: z.literal(["parliament", "court"]),
  approved: z.boolean(),
  vbar: z.number(),
  votes: z.record(
    z.string(), // key
    z.union([z.literal(0), z.literal(1), z.null()]), // value
  ),
});

export const StepResultSchema = z.union([
  CabinetStepResultSchema,
  VbarStepResultSchema,
]);

export const SimulationStateSchema = z.object({
  stepNo: z.number(),
  simulationId: z.number(),
  results: z.array(StepResultSchema),
});

export type SimulationState = z.infer<typeof SimulationStateSchema>;

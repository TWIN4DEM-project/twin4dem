import { z } from "zod";

export const SimulationStateSchema = z.object({
  t: z.number(),
  approved: z.boolean(),
  path: z.string(),
  votes: z.record(
    z.string(), // key
    z.union([z.literal(0), z.literal(1), z.null()]), // value
  ),
});

export type SimulationState = z.infer<typeof SimulationStateSchema>;

import { z } from "zod";

export const ActionSchema = z.object({
  action: z.string(),
});

export type Action = z.infer<typeof ActionSchema>;

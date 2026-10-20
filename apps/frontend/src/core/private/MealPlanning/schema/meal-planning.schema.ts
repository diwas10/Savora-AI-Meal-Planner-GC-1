import { z } from "zod";

export const generatePlanSchema = z.object({
  weekStart: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD format"),
});

export type GeneratePlanFormValues = z.infer<typeof generatePlanSchema>;

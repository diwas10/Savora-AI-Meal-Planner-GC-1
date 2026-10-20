import { z } from "zod";

export const cravingFormSchema = z.object({
  text: z
    .string()
    .min(1, "Please describe what you are craving")
    .max(500, "Maximum 500 characters"),
});

export type CravingFormValues = z.infer<typeof cravingFormSchema>;

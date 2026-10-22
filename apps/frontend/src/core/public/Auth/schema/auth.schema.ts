import { z } from "zod";

export const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  displayName: z.string().trim().min(1, "Tell us what to call you").max(120, "At most 120 characters"),
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "At least 8 characters").max(128, "At most 128 characters"),
});

export type RegisterFormValues = z.infer<typeof registerSchema>;

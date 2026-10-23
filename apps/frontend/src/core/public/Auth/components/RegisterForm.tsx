"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { registerSchema, type RegisterFormValues } from "../schema/auth.schema";
import { useRegisterMutation } from "../service/auth.query";
import { AuthLayout } from "./AuthLayout";
import { PasswordInput } from "./PasswordInput";

export function RegisterForm() {
  const router = useRouter();
  const registerUser = useRegisterMutation();
  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { displayName: "", email: "", password: "" },
  });
  const { errors } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    try {
      await registerUser.mutateAsync(values);
      router.replace("/onboarding");
    } catch (error) {
      if (error instanceof ApiError) {
        for (const [field, messages] of Object.entries(error.fieldErrors)) {
          if (field in values) form.setError(field as keyof RegisterFormValues, { message: messages[0] });
        }
      }
    }
  });

  const error = registerUser.error instanceof ApiError ? registerUser.error.message : registerUser.error ? "We couldn't create your account. Check your connection." : null;

  return (
    <AuthLayout title="Create your account" subtitle="A few questions next, then your first week.">
      <form noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
        {error && <InlineAlert tone="danger">{error}</InlineAlert>}
        <Field id="displayName" label="Your name" error={errors.displayName?.message}>
          <Input id="displayName" autoComplete="given-name" aria-invalid={Boolean(errors.displayName)} aria-describedby="displayName-error" {...form.register("displayName")} />
        </Field>
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" inputMode="email" aria-invalid={Boolean(errors.email)} aria-describedby="email-error" {...form.register("email")} />
        </Field>
        <Field id="password" label="Password" hint="At least 8 characters." error={errors.password?.message}>
          <PasswordInput id="password" autoComplete="new-password" aria-invalid={Boolean(errors.password)} aria-describedby="password-hint password-error" {...form.register("password")} />
        </Field>
        <Button type="submit" size="lg" block loading={registerUser.isPending} className="mt-2">
          Create account
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-primary">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

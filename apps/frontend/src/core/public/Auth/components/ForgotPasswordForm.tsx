"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { Button, LinkButton } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { forgotPasswordSchema, type ForgotPasswordFormValues } from "../schema/auth.schema";
import { useForgotPasswordMutation } from "../service/auth.query";
import { AuthLayout } from "./AuthLayout";

export function ForgotPasswordForm() {
  const forgot = useForgotPasswordMutation();
  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });
  const { errors } = form.formState;
  const submit = form.handleSubmit(async (values) => {
    await forgot.mutateAsync(values);
  });
  const error =
    forgot.error instanceof ApiError
      ? forgot.error.message
      : forgot.error
        ? "We couldn't reach the server. Check your connection."
        : null;

  if (forgot.isSuccess) {
    return (
      <AuthLayout title="Check your email" subtitle="Reset link on its way.">
        <div className="flex flex-col gap-4">
          <InlineAlert tone="success" icon={<MailCheck className="size-4" aria-hidden />}>
            If {form.getValues("email")} has a Savora account, we have sent a link to choose a new
            password. It works once and expires in an hour.
          </InlineAlert>
          <p className="text-sm text-muted-foreground">
            Nothing arrived? Look in your spam folder, or wait a minute and ask again.
          </p>
          <LinkButton href="/login" variant="secondary" size="lg" block>
            Back to sign in
          </LinkButton>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Forgot your password?" subtitle="Enter your email and we'll send you a reset link.">
      <form noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
        {error && <InlineAlert tone="danger">{error}</InlineAlert>}
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" inputMode="email" aria-invalid={Boolean(errors.email)} aria-describedby="email-error" {...form.register("email")} />
        </Field>
        <Button type="submit" size="lg" block loading={forgot.isPending} className="mt-2">
          Send reset link
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Remembered it?{" "}
          <Link href="/login" className="font-semibold text-primary">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

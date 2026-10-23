"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { Button, LinkButton } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { InlineAlert } from "@/components/ui/States";
import { ApiError } from "@/lib/api-request";
import { resetPasswordSchema, type ResetPasswordFormValues } from "../schema/auth.schema";
import { useResetPasswordMutation } from "../service/auth.query";
import { AuthLayout } from "./AuthLayout";
import { PasswordInput } from "./PasswordInput";

export function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const reset = useResetPasswordMutation();
  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirm: "" },
  });
  const { errors } = form.formState;

  const submit = form.handleSubmit(async (values) => {
    await reset.mutateAsync({ token, password: values.password });
    router.replace("/login?reset=1");
  });

  if (!token) {
    return (
      <AuthLayout title="Reset link missing" subtitle="Open the link from your email, or ask for a new one.">
        <LinkButton href="/forgot-password" size="lg" block>
          Send me a new link
        </LinkButton>
      </AuthLayout>
    );
  }

  const failed = reset.error instanceof ApiError && reset.error.status === 400;
  const error =
    reset.error instanceof ApiError ? reset.error.message : reset.error ? "We couldn't reach the server. Check your connection." : null;

  return (
    <AuthLayout title="Choose a new password" subtitle="At least 8 characters. You'll sign in with it next.">
      <form noValidate onSubmit={(e) => void submit(e)} className="flex flex-col gap-4">
        {error && (
          <InlineAlert tone="danger">
            {error}{" "}
            {failed && (
              <Link href="/forgot-password" className="font-semibold underline">
                Get a new link
              </Link>
            )}
          </InlineAlert>
        )}
        <Field id="password" label="New password" error={errors.password?.message}>
          <PasswordInput id="password" autoComplete="new-password" aria-invalid={Boolean(errors.password)} aria-describedby="password-error" {...form.register("password")} />
        </Field>
        <Field id="confirm" label="Confirm new password" error={errors.confirm?.message}>
          <PasswordInput id="confirm" autoComplete="new-password" aria-invalid={Boolean(errors.confirm)} aria-describedby="confirm-error" {...form.register("confirm")} />
        </Field>
        <Button type="submit" size="lg" block loading={reset.isPending} className="mt-2">
          Update password
        </Button>
      </form>
    </AuthLayout>
  );
}

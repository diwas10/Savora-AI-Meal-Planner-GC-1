"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { ApiError } from "@/lib/api-request";
import { loginSchema, type LoginFormValues } from "../schema/auth.schema";
import { useLoginMutation } from "../service/auth.query";

export function LoginForm() {
  const router = useRouter();
  const loginMutation = useLoginMutation();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    try {
      await loginMutation.mutateAsync(values);
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        for (const [field, messages] of Object.entries(err.fieldErrors)) {
          if (field === "email" || field === "password") {
            setError(field, { message: messages[0] });
          }
        }
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mx-auto w-full max-w-md space-y-5 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
    >
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Sign in to Savora</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Evidence-based meal planning and craving discovery
        </p>
      </div>

      {loginMutation.error instanceof Error && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          {loginMutation.error.message}
        </div>
      )}

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-neutral-800">
          Email address
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          {...register("email")}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
        />
        {errors.email && (
          <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-neutral-800">
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          {...register("password")}
          className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none"
        />
        {errors.password && (
          <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
        )}
      </div>

      <button
        type="submit"
        disabled={loginMutation.isPending}
        className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
      >
        {loginMutation.isPending ? "Signing in..." : "Sign in"}
      </button>

      <p className="text-center text-sm text-neutral-600">
        New to Savora?{" "}
        <Link href="/register" className="font-semibold text-emerald-700 hover:underline">
          Create an account
        </Link>
      </p>
    </form>
  );
}

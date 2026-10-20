import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 py-16 text-center">
      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-900">
        Savora GC1 · AI Meal Planning & Craving Discovery
      </span>
      <h1 className="mt-4 text-4xl font-extrabold tracking-tight text-neutral-900 sm:text-5xl">
        Personalized Weekly Meal Planning & Rule-Aware Craving Discovery
      </h1>
      <p className="mt-4 max-w-2xl text-base text-neutral-600">
        Configure your nutrition targets, select 3–5 seed dishes to anchor sequence
        recommendations, generate a 21-slot weekly plan verified by CSP, or explore
        natural-language cravings.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-4">
        <Link
          href="/login"
          className="rounded-lg bg-emerald-700 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-800"
        >
          Sign In
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-neutral-300 bg-white px-6 py-3 text-sm font-semibold text-neutral-800 hover:bg-neutral-50"
        >
          Create Account
        </Link>
      </div>
    </main>
  );
}

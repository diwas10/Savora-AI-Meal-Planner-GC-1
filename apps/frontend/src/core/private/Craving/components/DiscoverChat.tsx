"use client";

import type { Schema } from "@savora/contracts";
import { ArrowUp, Bot, Info, Repeat2, SearchX, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/Badge";
import { buttonVariants } from "@/components/ui/Button";
import { SuggestionChip } from "@/components/ui/Chip";
import { SafetyNotice } from "@/components/ui/SafetyNotice";
import { InlineAlert } from "@/components/ui/States";
import { useCurrentUserQuery } from "@/core/public/Auth/service/auth.query";
import { useOnline } from "@/hooks/useOnline";
import { ApiError } from "@/lib/api-request";
import { FLAVOR_LABEL, MEAL_LABEL, cuisineLabel, ingredientLabel, parseSlot } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { cravingFormSchema } from "../schema/craving.schema";
import type { CravingResponse } from "../service/craving.api";
import { useCravingMutation } from "../service/craving.query";
import { RecipeCard } from "./RecipeCard";
import { RecipeSheet } from "./RecipeSheet";
import { ThemeToggle } from "@/core/common/theme/ThemeToggle";

type CravingRequest = Schema<"CravingRequest">;
type CravingItem = Schema<"CravingItem">;
type ParseMeta = Schema<"CravingParseMeta">;

interface Message {
  id: string;
  role: "user" | "assistant";
  text?: string;
  response?: CravingResponse;
  error?: string;
}

const SUGGESTIONS = [
  "Something spicy and Chinese, without noodles",
  "A creamy Indian curry",
  "Nepali momo",
  "Something light and sour",
  "Korean, no pork",
  "Swap Tuesday dinner for something Thai",
];

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

function readChips(request: CravingRequest): string[] {
  return [
    ...(request.cuisineIds ?? []).map(cuisineLabel),
    ...(request.flavorTags ?? []).map((f) => FLAVOR_LABEL[f]),
    ...(request.excludedIngredientIds ?? []).map((x) => `no ${ingredientLabel(x)}`),
  ];
}

const PARSER_LABEL: Record<ParseMeta["parser"], string> = {
  HYBRID: "Read by local Qwen + patterns",
  QWEN: "Read by local Qwen",
  TEMPLATE: "Read by pattern matching",
};

/**
 * Discover (SCREENS.md): free-text cravings in a chat. Messages live only in this screen's
 * memory: Savora keeps no craving history. Results are standalone dishes (no plan change).
 */
export function DiscoverChat() {
  const user = useCurrentUserQuery();
  const mutation = useCravingMutation();
  const online = useOnline();
  const reduceMotion = useReducedMotion();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [openItem, setOpenItem] = useState<CravingItem | null>(null);
  const [itemOpen, setItemOpen] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "end" });
  }, [messages.length, mutation.isPending, reduceMotion]);

  const send = async (raw: string) => {
    const parsed = cravingFormSchema.safeParse({ text: raw.trim() });
    if (!parsed.success) {
      setInputError(parsed.error.issues[0]?.message ?? "Please describe what you'd like");
      return;
    }
    setInputError(null);
    const text = parsed.data.text;
    setMessages((m) => [...m, { id: nextId(), role: "user", text }]);
    setDraft("");
    try {
      const response = await mutation.mutateAsync({ text });
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text, response }]);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Something went wrong. Your message was kept; try sending it again.";
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text, error: message }]);
      setDraft(text); // preserve input after a recoverable failure
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(draft);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(draft);
    }
  };

  const firstName = user.data?.displayName.split(" ")[0];

  return (
    <div className="flex min-h-[calc(100dvh-8rem)] flex-col">
      <header className="flex items-center justify-between gap-3 pb-4 pt-6 lg:pt-10">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-hero-from via-hero-via to-hero-to text-hero-ink shadow-glow">
            <Sparkles className="size-5" aria-hidden />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Discover</h1>
            <p className="text-sm text-muted-foreground">Dishes for a craving, screened by your profile</p>
          </div>
        </div>
        <ThemeToggle />
      </header>

      <div className="flex flex-1 flex-col gap-4 pb-64 lg:pb-40" role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <motion.div variants={stagger} initial="hidden" animate="show" className="flex flex-col items-center px-2 py-8 text-center">
            <motion.div variants={fadeUp} className="relative mb-5">
              <span className="absolute inset-0 rounded-[28px] bg-primary-soft blur-xl motion-safe:animate-pulse-soft" aria-hidden />
              <span className="relative grid size-20 place-items-center rounded-[28px] bg-gradient-to-br from-hero-from via-hero-via to-hero-to text-hero-ink shadow-glow">
                <Bot className="size-9" aria-hidden />
              </span>
            </motion.div>
            <motion.h2 variants={fadeUp} className="text-xl font-semibold tracking-tight">
              {firstName ? `What are you craving, ${firstName}?` : "What are you craving?"}
            </motion.h2>
            <motion.p variants={fadeUp} className="mt-1.5 max-w-sm text-sm text-muted-foreground">
              Name a cuisine, a flavor or something to leave out. Your allergies and diet from your
              profile always apply.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-6 flex max-w-lg flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <SuggestionChip key={s} onClick={() => void send(s)} disabled={!online || mutation.isPending}>
                  {s}
                </SuggestionChip>
              ))}
            </motion.div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((m) =>
            m.role === "user" ? (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                className="ml-auto max-w-[85%] rounded-3xl rounded-br-lg bg-primary px-4 py-2.5 text-[15px] text-primary-foreground shadow-card"
              >
                {m.text}
              </motion.div>
            ) : (
              <motion.div key={m.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex max-w-full gap-2.5">
                <span className="mt-1 grid size-8 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary-soft-foreground">
                  <Bot className="size-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <AssistantReply message={m} onOpenItem={(item) => {
                    setOpenItem(item);
                    setItemOpen(true);
                  }} />
                </div>
              </motion.div>
            ),
          )}
        </AnimatePresence>

        {mutation.isPending && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2.5" aria-label="Savora is thinking">
            <span className="grid size-8 place-items-center rounded-xl bg-primary-soft text-primary-soft-foreground">
              <Bot className="size-4" aria-hidden />
            </span>
            <span className="flex gap-1 rounded-3xl rounded-bl-lg bg-surface px-4 py-3.5 ring-1 ring-border">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="size-2 rounded-pill bg-subtle-foreground"
                  animate={reduceMotion ? undefined : { y: [0, -4, 0], opacity: [0.5, 1, 0.5] }}
                  transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
                />
              ))}
            </span>
          </motion.div>
        )}
        <div ref={endRef} className="scroll-mb-64 lg:scroll-mb-40" />
      </div>

      {/* Composer: floats above the tab bar (mobile) or the page bottom (desktop). */}
      <form
        onSubmit={onSubmit}
        className="fixed inset-x-0 bottom-[calc(max(env(safe-area-inset-bottom),0.75rem)+5.25rem)] z-30 px-4 lg:bottom-6 lg:left-64"
      >
        <div className="mx-auto max-w-3xl">
          {inputError && (
            <p role="alert" className="mb-1.5 px-3 text-xs font-medium text-danger">
              {inputError}
            </p>
          )}
          {!online && (
            <p role="status" className="mb-1.5 px-3 text-xs font-medium text-warning-foreground">
              Discover needs a connection.
            </p>
          )}
          <div className="glass flex items-end gap-2 rounded-[26px] p-1.5 pl-4">
            <label htmlFor="craving-input" className="sr-only">
              Describe what you are craving
            </label>
            <textarea
              id="craving-input"
              ref={inputRef}
              rows={1}
              value={draft}
              maxLength={500}
              onChange={(e) => {
                setDraft(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
              }}
              onKeyDown={onKeyDown}
              placeholder="What are you craving?"
              aria-invalid={inputError ? true : undefined}
              className="max-h-36 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-[15px] text-foreground placeholder:text-subtle-foreground focus:outline-none"
            />
            <button
              type="submit"
              disabled={!online || mutation.isPending || !draft.trim()}
              aria-label="Send"
              className={cn(buttonVariants({ size: "icon" }), "shrink-0")}
            >
              <ArrowUp className="size-5" aria-hidden />
            </button>
          </div>
        </div>
      </form>

      <RecipeSheet item={openItem} open={itemOpen} onOpenChange={setItemOpen} />
    </div>
  );
}

function ParseLine({ parse, request }: { parse: ParseMeta; request: CravingRequest }) {
  const chips = readChips(request);
  return (
    <div className="mb-2 flex flex-wrap items-center gap-1.5" aria-label="How your message was read">
      {chips.map((c) => (
        <Badge key={c} tone="accent">
          {c}
        </Badge>
      ))}
      <span className="text-xs text-muted-foreground">{PARSER_LABEL[parse.parser]}</span>
    </div>
  );
}

function Bubble({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("w-fit max-w-full rounded-3xl rounded-tl-lg bg-surface px-4 py-3 text-[15px] leading-relaxed shadow-card ring-1 ring-border/70", className)}>
      {children}
    </div>
  );
}

function AssistantReply({ message, onOpenItem }: { message: Message; onOpenItem: (item: CravingItem) => void }) {
  if (message.error) {
    return (
      <InlineAlert tone="danger" title="I couldn't answer that">
        {message.error}
      </InlineAlert>
    );
  }
  const response = message.response;
  if (!response) return null;

  // `kind` is optional in the generated types, so narrow on the payload instead.
  if (!("result" in response)) {
    const slot = response.request.mealSlotId ? parseSlot(response.request.mealSlotId) : null;
    const href = `/meal-plans?swap=${response.request.mealSlotId ?? ""}&text=${encodeURIComponent(message.text ?? "")}`;
    return (
      <div className="flex flex-col gap-2">
        <ParseLine parse={response.parse} request={response.request} />
        {slot ? (
          <Bubble>
            <p>
              Sounds like you want to change a planned meal: <strong>day {slot.day} {MEAL_LABEL[slot.meal].toLowerCase()}</strong>.
              Swaps are checked against your whole week, so they happen in My Plan.
            </p>
            <Link href={href} className={cn(buttonVariants({ size: "sm" }), "mt-3")}>
              <Repeat2 className="size-4" aria-hidden /> Open the swap
            </Link>
          </Bubble>
        ) : (
          <Bubble>{response.clarification ?? "Which planned meal would you like to swap? Name the day and the meal."}</Bubble>
        )}
      </div>
    );
  }

  const result = response.result;
  const clarification = response.parse.clarification;
  return (
    <div className="flex flex-col gap-2.5">
      <ParseLine parse={response.parse} request={result.request} />
      {result.status === "NEEDS_CLARIFICATION" && <Bubble>{clarification ?? "Could you tell me a cuisine or flavor?"}</Bubble>}

      {result.status === "NO_MATCH" && (
        <Bubble>
          <p className="flex items-center gap-2 font-semibold">
            <SearchX className="size-4" aria-hidden /> No dish fits that and your profile
          </p>
          <ul className="mt-1.5 list-disc pl-5 text-sm text-muted-foreground">
            {result.unknownCuisineIds.length > 0 && (
              <li>{result.unknownCuisineIds.map(cuisineLabel).join(", ")} isn&apos;t in the catalogue yet.</li>
            )}
            {result.unmatchedFlavorTags.length > 0 && (
              <li>No allowed dish is {result.unmatchedFlavorTags.map((f) => FLAVOR_LABEL[f].toLowerCase()).join(" or ")}.</li>
            )}
            <li>Your diet, allergies and exclusions always apply, which can leave nothing. Try a different cuisine or fewer exclusions.</li>
          </ul>
        </Bubble>
      )}

      {result.status === "OK" && (
        <>
          <Bubble>
            Here {result.items.length === 1 ? "is a dish" : `are ${result.items.length} dishes`} your profile allows, best match first.
            {result.unmatchedFlavorTags.length > 0 &&
              ` (Nothing was ${result.unmatchedFlavorTags.map((f) => FLAVOR_LABEL[f].toLowerCase()).join(" or ")}, so I relaxed that.)`}
          </Bubble>
          <motion.ul variants={stagger} initial="hidden" animate="show" className="flex flex-col gap-2">
            {result.items.map((item) => (
              <RecipeCard key={item.recipeId} item={item} onOpen={() => onOpenItem(item)} />
            ))}
          </motion.ul>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Info className="size-3.5" aria-hidden /> Standard portions. Not checked against today&apos;s remaining targets.
            {result.fallbackReason === "MODEL_UNAVAILABLE" && " Ranked by popularity."}
          </p>
        </>
      )}
      <SafetyNotice safety={result.safety} compact />
    </div>
  );
}

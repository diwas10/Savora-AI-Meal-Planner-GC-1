import type { Transition, Variants } from "motion/react";

/** Short, calm transitions (DESIGN_SYSTEM: motion clarifies state, never delays tasks). */
export const spring: Transition = { type: "spring", stiffness: 420, damping: 34, mass: 0.8 };
export const gentle: Transition = { type: "spring", stiffness: 260, damping: 30 };
export const quick: Transition = { duration: 0.18, ease: [0.2, 0.8, 0.2, 1] };

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: gentle },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05, delayChildren: 0.04 } },
};

export const pop: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: spring },
};

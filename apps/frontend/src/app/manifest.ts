import type { MetadataRoute } from "next";

/** Installable PWA manifest (DESIGN_SYSTEM: installable, standalone, app icons). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Savora: explainable meal planning",
    short_name: "Savora",
    description: "7-day meal plans that fit your cuisines, rules and allergies, with reasons.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f7f5f0",
    theme_color: "#1f6b54",
    categories: ["food", "health", "lifestyle"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "My Plan", url: "/meal-plans", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Discover", url: "/discover", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}

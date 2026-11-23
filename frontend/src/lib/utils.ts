import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Assemble des classes Tailwind ; en cas de conflit (ex. "p-2" puis "p-4"), la dernière gagne. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 0.1234 -> "12,3 %" (format français) */
export const pct = (v: number, digits = 1) => (v * 100).toFixed(digits).replace(".", ",") + " %";

/** 1.23456 -> "1,235" */
export const num = (v: number, digits = 3) => v.toFixed(digits).replace(".", ",").replace("-", "−");

export const formatBytes = (b: number) =>
  b < 1024 ? `${b} o` : b < 1024 ** 2 ? `${(b / 1024).toFixed(0)} Ko` : `${(b / 1024 ** 2).toFixed(1).replace(".", ",")} Mo`;

export const formatCount = (n: number) => n.toLocaleString("fr-FR");

/** Nom affiché d'une source d'image */
export const sourceLabel = { dataset: "Base GHIM-10K", upload: "Importée", transform: "Transformée" } as const;

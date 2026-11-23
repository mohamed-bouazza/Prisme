/**
 * Composants d'interface réutilisables (boutons, champs, fenêtre modale...), au style « Prisme ».
 * Toutes les pages les utilisent : le design reste cohérent et se modifie à un seul endroit.
 */
import { Loader2, X } from "lucide-react";
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  useEffect,
  useId,
  useRef,
} from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

// ------------------------------------------------------------------------- bouton
const variants = {
  primary: "bg-primary text-white hover:bg-primary-hover disabled:bg-primary/50",
  secondary: "bg-white text-ink border border-line-strong hover:bg-canvas disabled:text-muted",
  ghost: "bg-transparent text-ink hover:bg-ink/5",
  danger: "bg-reject-soft text-reject-ink hover:bg-[#fbd5ca]",
  dark: "bg-ink-2 text-white hover:bg-[#26314a]",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
};

/** Classes d'un bouton : aussi utilisées pour un lien <a> qui doit ressembler à un bouton. */
export function buttonClass(variant: keyof typeof variants = "primary", size: "sm" | "md" | "lg" = "md", className?: string) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-xl font-semibold no-underline transition-colors cursor-pointer disabled:cursor-not-allowed",
    size === "sm" && "h-9 px-3 text-[13px] rounded-[10px]",
    size === "md" && "h-11 px-4 text-sm",
    size === "lg" && "h-12 px-5 text-[15px]",
    variants[variant],
    className,
  );
}

export function Button({ variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={buttonClass(variant, size, className)}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn("inline-flex size-10 items-center justify-center rounded-[10px] text-muted hover:bg-ink/5 hover:text-ink cursor-pointer", className)}
      {...rest}
    >
      {children}
    </button>
  );
}

// -------------------------------------------------------------------------- champs
export function Field({ label, hint, children, htmlFor }: { label: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={htmlFor} className="text-[13px] font-semibold">
          {label}
        </label>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

const fieldClass =
  "h-11 w-full rounded-xl border border-line-strong bg-white px-3.5 text-[15px] text-ink placeholder:text-muted/80 focus:border-primary focus:ring-[3px] focus:ring-primary/15 focus:outline-none";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldClass, className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(fieldClass, "px-3 cursor-pointer", className)} {...rest}>
      {children}
    </select>
  );
}

// ---------------------------------------------------- choix segmenté (onglets compacts)
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex rounded-[10px] bg-[#eceef4] p-[3px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-[34px] cursor-pointer rounded-lg px-3.5 text-[13px]",
            o.value === value ? "bg-white font-semibold text-ink shadow-[0_1px_2px_rgba(14,21,37,.08)]" : "font-medium text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------- fenêtre modale
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = "max-w-[560px]",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  // onClose change à chaque rendu du parent : on le garde dans une ref pour que l'effet ci-dessous
  // ne se relance qu'à l'ouverture (sinon le focus sauterait à chaque frappe).
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    // Focus sur le premier CHAMP (pas sur le bouton « Fermer », sinon Entrée fermerait la fenêtre)
    const p = panel.current;
    (p?.querySelector<HTMLElement>("input:not(.sr-only), select, textarea") ?? p?.querySelector<HTMLElement>("button"))?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus(); // on rend le focus à l'élément qui a ouvert la fenêtre
    };
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/55 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn("flex w-full flex-col gap-5 rounded-[22px] bg-white p-7 shadow-[0_40px_80px_-24px_rgba(14,21,37,.45)]", width)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h2 id={titleId} className="font-display text-2xl font-semibold">
              {title}
            </h2>
            {description && <p className="text-sm text-muted">{description}</p>}
          </div>
          <IconButton label="Fermer" onClick={onClose} className="bg-[#f1f3f8] text-ink">
            <X className="size-[18px]" />
          </IconButton>
        </div>
        {children}
        {footer && <div className="flex flex-wrap justify-end gap-2.5">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

// ------------------------------------------------------------------- petits éléments
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-6 animate-spin text-primary", className)} aria-label="Chargement" />;
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[18px] border border-dashed border-line-strong bg-white px-6 py-16 text-center">
      <span className="flex size-12 items-center justify-center rounded-[14px] bg-primary-soft text-primary">{icon}</span>
      <p className="font-display text-lg font-semibold">{title}</p>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("rounded-[18px] border border-line bg-white", className)}>{children}</section>;
}

export function Badge({ children, tone = "primary" }: { children: ReactNode; tone?: "primary" | "muted" | "ok" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        tone === "primary" && "bg-primary-soft text-primary-hover",
        tone === "muted" && "bg-[#eef0f5] text-muted",
        tone === "ok" && "bg-ok-soft text-ok",
      )}
    >
      {children}
    </span>
  );
}

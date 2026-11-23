/** Vignette d'une image dans une grille, avec case de sélection optionnelle. */
import { Check } from "lucide-react";
import { Link } from "react-router";

import type { ImageItem } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ImageCard({
  image,
  categoryName,
  selected,
  onToggle,
}: {
  image: ImageItem;
  categoryName?: string;
  selected?: boolean;
  onToggle?: () => void;
}) {
  return (
    <article
      className={cn(
        "group overflow-hidden rounded-[14px] bg-white transition-shadow",
        selected ? "border-2 border-primary shadow-[0_0_0_4px_rgba(67,56,202,.15)]" : "border border-line hover:shadow-[0_12px_24px_-16px_rgba(14,21,37,.35)]",
      )}
    >
      <div className="relative">
        <Link to={`/images/${image.id}`} className="block" aria-label={`Ouvrir ${image.filename}`}>
          <img src={image.urls.thumb} alt={image.filename} loading="lazy" className="block aspect-[4/3] w-full bg-[#eef0f5] object-cover" />
        </Link>
        {onToggle && (
          <button
            type="button"
            role="checkbox"
            aria-checked={selected}
            aria-label={`Sélectionner ${image.filename}`}
            onClick={onToggle}
            className={cn(
              "absolute top-2.5 left-2.5 flex size-6 cursor-pointer items-center justify-center rounded-[7px] border-2 transition-opacity",
              selected ? "border-primary bg-primary opacity-100" : "border-white bg-white/85 opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
            )}
          >
            {selected && <Check className="size-3.5 text-white" strokeWidth={3.2} />}
          </button>
        )}
        {!image.public && (
          <span className="absolute top-2.5 right-2.5 rounded-md bg-ink/75 px-2 py-0.5 text-[11px] font-semibold text-white">
            {image.source === "transform" ? "Transformée" : "Importée"}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1 px-3.5 py-3">
        <span className="truncate text-sm font-semibold">{image.filename}</span>
        <span className="truncate text-xs text-muted">
          {categoryName ?? "Sans catégorie"} · {image.width} × {image.height}
        </span>
      </div>
    </article>
  );
}

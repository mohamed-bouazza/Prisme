/**
 * Choix de la catégorie où ranger une image : « Mes catégories » + « Base GHIM-10K »,
 * avec un bouton pour créer une catégorie sans quitter l'écran (elle est alors sélectionnée).
 */
import { Plus } from "lucide-react";
import { useState } from "react";

import { CategoryDialog } from "@/components/CategoryDialog";
import { Select } from "@/components/ui";
import { categoryOptions, useCategories } from "@/lib/hooks";

export function CategorySelect({
  id,
  value,
  onChange,
}: {
  id: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  const { data: categories = [] } = useCategories();
  const [creating, setCreating] = useState(false);
  const all = categoryOptions(categories);
  const mine = all.filter((o) => !o.public);
  const pub = all.filter((o) => o.public);

  return (
    <div className="flex flex-col gap-1.5">
      <Select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">Sans catégorie</option>
        {mine.length > 0 && (
          <optgroup label="Mes catégories">
            {mine.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </optgroup>
        )}
        {pub.length > 0 && (
          <optgroup label="Base GHIM-10K">
            {pub.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </optgroup>
        )}
      </Select>
      <button
        type="button"
        onClick={() => setCreating(true)}
        className="inline-flex w-fit cursor-pointer items-center gap-1.5 border-0 bg-transparent p-0 text-[13px] font-semibold text-primary hover:text-primary-hover"
      >
        <Plus className="size-3.5" aria-hidden />
        Nouvelle catégorie
      </button>
      <CategoryDialog open={creating} onClose={() => setCreating(false)} onCreated={(c) => onChange(c.id)} />
    </div>
  );
}

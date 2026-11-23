/** Requêtes partagées entre plusieurs composants (mises en cache par TanStack Query). */
import { useQuery } from "@tanstack/react-query";

import { api, type Category } from "@/lib/api";

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: () => api.categories().then((r) => r.categories) });
}

export type CategoryNode = Category & { children: CategoryNode[]; depth: number };

/** Liste à plat (id, parent_id) -> arbre. Les publiques (GHIM-10K) d'abord, puis par nom. */
export function buildTree(categories: Category[]): CategoryNode[] {
  const nodes = new Map<number, CategoryNode>();
  categories.forEach((c) => nodes.set(c.id, { ...c, children: [], depth: 0 }));
  const roots: CategoryNode[] = [];
  nodes.forEach((n) => {
    const parent = n.parent_id !== null ? nodes.get(n.parent_id) : undefined;
    (parent ? parent.children : roots).push(n);
  });
  const sort = (list: CategoryNode[], depth: number) => {
    list.sort((a, b) => Number(b.public) - Number(a.public) || a.name.localeCompare(b.name, "fr"));
    list.forEach((n) => {
      n.depth = depth;
      sort(n.children, depth + 1);
    });
  };
  sort(roots, 0);
  return roots;
}

/** Liste « aplatie » pour un <select> : chaque catégorie avec son chemin complet. */
export function categoryOptions(categories: Category[], onlyMine = false): { id: number; label: string; public: boolean }[] {
  const byId = new Map(categories.map((c) => [c.id, c]));
  const path = (c: Category): string => {
    const parent = c.parent_id !== null ? byId.get(c.parent_id) : undefined;
    return parent ? `${path(parent)} / ${c.name}` : c.name;
  };
  return categories
    .filter((c) => !onlyMine || !c.public)
    .map((c) => ({ id: c.id, label: path(c), public: c.public }))
    .sort((a, b) => a.label.localeCompare(b.label, "fr"));
}

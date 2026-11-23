/** Fenêtre de création / renommage d'une catégorie (avec choix de la catégorie parente). */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button, Field, Input, Modal, Select } from "@/components/ui";
import { api, type Category } from "@/lib/api";
import { categoryOptions, useCategories } from "@/lib/hooks";

export function CategoryDialog({
  open,
  onClose,
  editing,
  defaultParent = null,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  editing?: Category | null;
  defaultParent?: number | null;
  onCreated?: (c: Category) => void;
}) {
  const qc = useQueryClient();
  const { data: categories = [] } = useCategories();
  const [name, setName] = useState("");
  const [parent, setParent] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setName(editing?.name ?? "");
      setParent(editing ? editing.parent_id : defaultParent);
    }
  }, [open, editing, defaultParent]);

  const save = useMutation({
    mutationFn: () =>
      editing ? api.updateCategory(editing.id, { name, parent_id: parent }) : api.createCategory(name, parent),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["categories"] });
      toast.success(editing ? "Catégorie modifiée" : `Catégorie « ${name} » créée`);
      if (!editing) onCreated?.(r.category);
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // On ne peut ranger une catégorie que dans ses propres catégories (le backend refuse aussi les cycles)
  const options = categoryOptions(categories, true).filter((o) => o.id !== editing?.id);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) save.mutate();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Modifier la catégorie" : "Nouvelle catégorie"}
      description="Les catégories peuvent contenir des sous-catégories."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" form="category-form" loading={save.isPending} disabled={!name.trim()}>
            {editing ? "Enregistrer" : "Créer"}
          </Button>
        </>
      }
    >
      <form id="category-form" onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Nom" htmlFor="cat-name">
          <Input id="cat-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="Ex. Voyages" />
        </Field>
        <Field label="Ranger dans" htmlFor="cat-parent">
          <Select id="cat-parent" value={parent ?? ""} onChange={(e) => setParent(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Aucune (catégorie principale)</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

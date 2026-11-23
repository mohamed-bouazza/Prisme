/**
 * Import d'une ou plusieurs images (glisser-déposer ou sélection de fichiers).
 * Les fichiers sont envoyés UN PAR UN (3 en parallèle) : chacun a son propre état
 * (en attente, en cours, importé, refusé) et une erreur n'empêche pas les autres.
 */
import { useQueryClient } from "@tanstack/react-query";
import { Check, FileX2, ImageUp, Loader2 } from "lucide-react";
import { type DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { CategorySelect } from "@/components/CategorySelect";
import { Button, Field, Modal } from "@/components/ui";
import { api } from "@/lib/api";
import { useCategories } from "@/lib/hooks";
import { cn, formatBytes } from "@/lib/utils";

type Item = { file: File; preview: string; status: "pending" | "uploading" | "done" | "error"; message?: string; id?: number };

const ACCEPT = "image/jpeg,image/png,image/webp,image/bmp,image/tiff,image/gif";
const MAX_MB = 20;

export function UploadDialog({ open, onClose, defaultCategory }: { open: boolean; onClose: () => void; defaultCategory: number | null }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: categories = [] } = useCategories();
  const [items, setItems] = useState<Item[]>([]);
  const [category, setCategory] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setItems([]);
      // on propose la catégorie ouverte dans la galerie (la sienne ou une catégorie de GHIM-10K)
      setCategory(categories.some((c) => c.id === defaultCategory) ? defaultCategory : null);
    }
  }, [open]); // seulement à l'ouverture de la fenêtre
  useEffect(() => () => items.forEach((i) => URL.revokeObjectURL(i.preview)), [items]);

  const update = (file: File, patch: Partial<Item>) =>
    setItems((list) => list.map((i) => (i.file === file ? { ...i, ...patch } : i)));

  const uploadOne = async (file: File) => {
    if (file.size > MAX_MB * 1024 * 1024) return update(file, { status: "error", message: `Refusée : plus de ${MAX_MB} Mo` });
    update(file, { status: "uploading" });
    try {
      const r = await api.upload([file], category);
      if (r.images.length) {
        update(file, { status: "done", id: r.images[0].id, message: r.warnings[0] ?? (r.images[0].indexed ? "Importée et indexée" : "Importée") });
      } else {
        update(file, { status: "error", message: "Refusée : " + (r.errors[0]?.error ?? "erreur inconnue") });
      }
    } catch (e) {
      update(file, { status: "error", message: "Refusée : " + (e as Error).message });
    }
  };

  const addFiles = async (files: File[]) => {
    const fresh = files.map((file) => ({ file, preview: URL.createObjectURL(file), status: "pending" as const }));
    setItems((list) => [...list, ...fresh]);
    const queue = [...files];
    const worker = async () => {
      for (let f = queue.shift(); f; f = queue.shift()) await uploadOne(f);
    };
    await Promise.all([worker(), worker(), worker()]); // 3 envois en parallèle au maximum
    qc.invalidateQueries({ queryKey: ["images"] });
    qc.invalidateQueries({ queryKey: ["categories"] });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const done = items.filter((i) => i.status === "done").length;
  const errors = items.filter((i) => i.status === "error").length;
  const running = items.filter((i) => i.status === "uploading" || i.status === "pending").length;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Importer des images"
      description={`JPEG, PNG, WebP, BMP, TIFF ou GIF · ${MAX_MB} Mo maximum par fichier`}
      width="max-w-[640px]"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <span className="text-[13px] text-muted">
            {items.length ? `${done} importée(s) · ${running} en cours · ${errors} refusée(s)` : "Aucun fichier"}
          </span>
          <div className="flex gap-2.5">
            <Button variant="secondary" onClick={onClose}>
              Fermer
            </Button>
            <Button
              disabled={!done || running > 0}
              onClick={() => {
                onClose();
                navigate(category ? `/?cat=${category}` : "/?scope=mine");
              }}
            >
              Voir dans la galerie
            </Button>
          </div>
        </div>
      }
    >
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative flex cursor-pointer flex-col items-center gap-2.5 rounded-2xl border-2 border-dashed px-5 py-8 text-center transition-colors",
          dragging ? "border-primary bg-primary-soft" : "border-primary-light bg-[#f7f7ff] hover:bg-primary-soft",
        )}
      >
        <span className="flex size-[52px] items-center justify-center rounded-[14px] bg-primary-soft text-primary">
          <ImageUp className="size-[26px]" aria-hidden />
        </span>
        <span className="text-base font-semibold">Déposez vos images ici</span>
        <span className="text-sm text-muted">
          ou <span className="font-semibold text-primary underline">parcourez vos fichiers</span>, plusieurs à la fois
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          onChange={(e) => {
            addFiles(Array.from(e.target.files ?? []));
            e.target.value = ""; // permet de reprendre le même fichier
          }}
        />
      </label>

      <Field label="Catégorie de destination" htmlFor="up-cat">
        <CategorySelect id="up-cat" value={category} onChange={setCategory} />
      </Field>

      {items.length > 0 && (
        <ul className="m-0 flex max-h-[280px] list-none flex-col gap-2.5 overflow-y-auto p-0">
          {items.map((it) => (
            <li
              key={it.preview}
              className={cn(
                "flex items-center gap-3.5 rounded-[14px] border p-2.5",
                it.status === "error" ? "border-[#f6c9b8] bg-[#fff6f2]" : "border-line",
              )}
            >
              {it.status === "error" ? (
                <span className="flex h-[42px] w-14 items-center justify-center rounded-lg bg-reject-soft text-reject-ink">
                  <FileX2 className="size-5" aria-hidden />
                </span>
              ) : (
                <img src={it.preview} alt="" className="h-[42px] w-14 rounded-lg object-cover" />
              )}
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex justify-between gap-3 text-sm">
                  <span className="truncate font-semibold">{it.file.name}</span>
                  <span className="shrink-0 text-xs text-muted">{formatBytes(it.file.size)}</span>
                </div>
                {it.status === "uploading" || it.status === "pending" ? (
                  <div className="h-1.5 overflow-hidden rounded-full bg-[#eef0f5]">
                    <div className={cn("h-full rounded-full bg-primary", it.status === "uploading" ? "w-2/3 animate-pulse" : "w-0")} />
                  </div>
                ) : (
                  <span className={cn("text-xs", it.status === "error" ? "text-reject-ink" : "text-muted")}>{it.message}</span>
                )}
              </div>
              {it.status === "done" && (
                <span className="flex size-7 items-center justify-center rounded-full bg-ok-soft text-ok" aria-label="Importée">
                  <Check className="size-4" strokeWidth={2.8} />
                </span>
              )}
              {it.status === "uploading" && <Loader2 className="size-5 animate-spin text-primary" aria-label="En cours" />}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

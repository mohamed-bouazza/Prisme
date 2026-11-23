/**
 * Galerie : images filtrées (catégorie, propriétaire, nom), sélection multiple
 * (télécharger en ZIP, déplacer, supprimer), import, et recherche par une image envoyée.
 *
 * Les filtres sont dans l'URL (?cat=7&scope=mine&q=...&page=2) : on peut partager le lien,
 * et le bouton « Précédent » du navigateur fonctionne.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FolderInput, ImageIcon, ImageUp, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { CategorySelect } from "@/components/CategorySelect";
import { ImageCard } from "@/components/ImageCard";
import { Pagination } from "@/components/Pagination";
import { Button, EmptyState, Field, IconButton, Modal, Segmented, Spinner } from "@/components/ui";
import { UploadDialog } from "@/components/UploadDialog";
import { api, saveBlob } from "@/lib/api";
import { useCategories } from "@/lib/hooks";
import { formatCount } from "@/lib/utils";

type Scope = "all" | "mine" | "public";
const PER_PAGE = 40;

export function GalleryPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const cat = Number(params.get("cat")) || null;
  const scope = (params.get("scope") as Scope) || "all";
  const q = params.get("q") ?? "";
  const order = params.get("order") ?? "newest";
  const page = Number(params.get("page")) || 1;

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page"); // un nouveau filtre ramène à la page 1
    setParams(next);
  };

  // Champ de recherche par nom : on attend 300 ms après la dernière frappe avant d'interroger l'API
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  useEffect(() => {
    const t = setTimeout(() => text !== q && setParam("q", text.trim() || null), 300);
    return () => clearTimeout(t);
  }, [text]); // volontairement : on ne réagit qu'à la frappe, pas aux changements d'URL

  const { data: categories = [] } = useCategories();
  const catById = useMemo(() => new Map(categories.map((c) => [c.id, c])), [categories]);
  const current = cat ? catById.get(cat) : undefined;

  const images = useQuery({
    queryKey: ["images", { cat, scope, q, order, page }],
    queryFn: () => api.images({ category_id: cat, scope, q, order, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData, // garde la page précédente affichée pendant le chargement
  });

  // ------------------------------------------------------------------ sélection
  const [selected, setSelected] = useState<Set<number>>(new Set());
  useEffect(() => setSelected(new Set()), [cat, scope, q, page]);
  const toggle = (id: number) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const items = images.data?.items ?? [];
  const selectedItems = items.filter((i) => selected.has(i.id));
  const allMine = selectedItems.length > 0 && selectedItems.every((i) => i.mine);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["images"] });
    qc.invalidateQueries({ queryKey: ["categories"] });
  };

  const remove = useMutation({
    mutationFn: () => api.deleteImages([...selected]),
    onSuccess: (r) => {
      toast.success(`${r.deleted.length} image(s) supprimée(s)`);
      r.warnings.forEach((w) => toast.warning(w));
      setSelected(new Set());
      setConfirmDelete(false);
      refresh();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const zip = useMutation({
    mutationFn: () => api.downloadZip([...selected]),
    onSuccess: (blob) => saveBlob(blob, "images.zip"),
    onError: (e: Error) => toast.error(e.message),
  });

  // Recherche par une image qui n'est pas dans la galerie : on la passe à la page Recherche
  const queryFile = useRef<HTMLInputElement>(null);

  const title = current ? current.name : scope === "mine" ? "Mes images" : scope === "public" ? "Base GHIM-10K" : "Toutes les images";
  const path = useMemo(() => {
    const out = [];
    for (let c = current; c; c = c.parent_id !== null ? catById.get(c.parent_id) : undefined) out.unshift(c);
    return out;
  }, [current, catById]);

  return (
    <>
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-white px-8 py-4">
        <label className="flex h-11 max-w-[520px] flex-[1_1_320px] items-center gap-2.5 rounded-xl border border-line-strong bg-[#f9fafc] px-3.5 text-muted focus-within:border-primary">
          <Search className="size-[18px]" aria-hidden />
          <input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Rechercher un nom de fichier"
            aria-label="Rechercher un nom de fichier"
            className="flex-1 border-0 bg-transparent text-[15px] text-ink outline-none"
          />
        </label>
        <div className="ml-auto flex gap-2.5">
          <Button variant="secondary" icon={<ImageIcon className="size-[18px]" />} onClick={() => queryFile.current?.click()}>
            Chercher par image
          </Button>
          <input
            ref={queryFile}
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) navigate("/recherche", { state: { file: f } });
            }}
          />
          <Button icon={<ImageUp className="size-[18px]" />} onClick={() => setUploadOpen(true)}>
            Importer
          </Button>
        </div>
      </header>

      <div className="flex flex-col gap-5 px-8 pt-7 pb-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <nav aria-label="Fil d'Ariane" className="text-[13px] text-muted">
              <Link to="/" className="text-muted no-underline hover:text-ink">
                Galerie
              </Link>
              {path.map((c) => (
                <span key={c.id}>
                  {" / "}
                  <Link to={`/?cat=${c.id}`} className="text-muted no-underline hover:text-ink">
                    {c.name}
                  </Link>
                </span>
              ))}
            </nav>
            <h1 className="m-0 font-display text-[32px] font-semibold tracking-[-0.02em]">
              {title}{" "}
              <span className="text-lg font-medium text-muted">{images.data ? formatCount(images.data.total) : ""}</span>
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented<Scope>
              label="Filtrer par propriétaire"
              value={scope}
              onChange={(v) => setParam("scope", v === "all" ? null : v)}
              options={[
                { value: "all", label: "Toutes" },
                { value: "mine", label: "Mes images" },
                { value: "public", label: "Base GHIM-10K" },
              ]}
            />
            <label className="flex h-10 items-center gap-2 rounded-[10px] border border-line-strong bg-white px-3 text-[13px] text-muted">
              Trier
              <select value={order} onChange={(e) => setParam("order", e.target.value === "newest" ? null : e.target.value)} className="cursor-pointer border-0 bg-transparent text-[13px] font-semibold text-ink outline-none">
                <option value="newest">Plus récentes</option>
                <option value="oldest">Plus anciennes</option>
                <option value="name">Nom</option>
              </select>
            </label>
          </div>
        </div>

        {selected.size > 0 && (
          <div className="sticky top-3 z-10 flex flex-wrap items-center gap-3 rounded-[14px] bg-ink py-2.5 pr-3 pl-[18px] text-white shadow-[0_16px_32px_-16px_rgba(14,21,37,.6)]">
            <span className="text-sm font-semibold">{selected.size} image(s) sélectionnée(s)</span>
            <div className="ml-auto flex flex-wrap gap-2">
              <Button variant="dark" size="sm" loading={zip.isPending} icon={<Download className="size-4" />} onClick={() => zip.mutate()}>
                Télécharger (ZIP)
              </Button>
              <Button variant="dark" size="sm" disabled={!allMine} title={allMine ? undefined : "Seules vos images peuvent être déplacées"} icon={<FolderInput className="size-4" />} onClick={() => setMoveOpen(true)}>
                Déplacer
              </Button>
              <Button variant="danger" size="sm" disabled={!allMine} title={allMine ? undefined : "Les images de la base GHIM-10K sont en lecture seule"} icon={<Trash2 className="size-4" />} onClick={() => setConfirmDelete(true)}>
                Supprimer
              </Button>
              <IconButton label="Annuler la sélection" onClick={() => setSelected(new Set())} className="text-side-text hover:bg-ink-2 hover:text-white">
                <X className="size-[18px]" />
              </IconButton>
            </div>
          </div>
        )}

        {images.isPending ? (
          <div className="flex justify-center py-24">
            <Spinner />
          </div>
        ) : images.isError ? (
          <EmptyState icon={<X className="size-6" />} title="Impossible de charger les images">
            {(images.error as Error).message}
          </EmptyState>
        ) : items.length === 0 ? (
          <EmptyState icon={<ImageIcon className="size-6" />} title="Aucune image ici">
            {q ? "Aucun nom de fichier ne correspond à cette recherche." : "Importez vos premières images avec le bouton « Importer »."}
          </EmptyState>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-[18px]">
            {items.map((im) => (
              <ImageCard
                key={im.id}
                image={im}
                categoryName={im.category_id ? catById.get(im.category_id)?.name : undefined}
                selected={selected.has(im.id)}
                onToggle={() => toggle(im.id)}
              />
            ))}
          </div>
        )}

        {images.data && images.data.total > 0 && (
          <Pagination page={page} pages={images.data.pages} total={images.data.total} perPage={PER_PAGE} onChange={(p) => setParam("page", p === 1 ? null : String(p))} />
        )}
      </div>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} defaultCategory={cat} />
      <MoveDialog open={moveOpen} onClose={() => setMoveOpen(false)} ids={[...selected]} onDone={() => { setSelected(new Set()); refresh(); }} />
      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={`Supprimer ${selected.size} image(s) ?`}
        description="Les fichiers et leurs miniatures sont supprimés, et les images retirées de l'index de recherche. Cette action est définitive."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
              Annuler
            </Button>
            <Button variant="danger" loading={remove.isPending} icon={<Trash2 className="size-4" />} onClick={() => remove.mutate()}>
              Supprimer définitivement
            </Button>
          </>
        }
      >
        {null}
      </Modal>
    </>
  );
}

function MoveDialog({ open, onClose, ids, onDone }: { open: boolean; onClose: () => void; ids: number[]; onDone: () => void }) {
  const [target, setTarget] = useState<number | null>(null);
  const move = useMutation({
    mutationFn: () => Promise.all(ids.map((id) => api.updateImage(id, { category_id: target }))),
    onSuccess: () => {
      toast.success(`${ids.length} image(s) déplacée(s)`);
      onDone();
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Déplacer ${ids.length} image(s)`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Annuler
          </Button>
          <Button loading={move.isPending} onClick={() => move.mutate()}>
            Déplacer
          </Button>
        </>
      }
    >
      <Field label="Vers la catégorie" htmlFor="move-cat">
        <CategorySelect id="move-cat" value={target} onChange={setTarget} />
      </Field>
    </Modal>
  );
}

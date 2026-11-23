/** Détail d'une image : aperçu, informations, actions, et ses descripteurs. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Crop, Download, RefreshCw, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { CategorySelect } from "@/components/CategorySelect";
import { DescriptorsPanel } from "@/components/DescriptorsPanel";
import { Button, buttonClass, EmptyState, Field, Input, Modal, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatBytes, sourceLabel } from "@/lib/utils";

export function ImagePage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["image", id], queryFn: () => api.image(id).then((r) => r.image) });
  const image = q.data;

  const [name, setName] = useState("");
  const [cat, setCat] = useState<number | null>(null);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    if (image) {
      setName(image.filename);
      setCat(image.category_id);
    }
  }, [image]);

  const save = useMutation({
    mutationFn: () => api.updateImage(id, { filename: name, category_id: cat }),
    onSuccess: () => {
      toast.success("Modifications enregistrées");
      qc.invalidateQueries({ queryKey: ["image", id] });
      qc.invalidateQueries({ queryKey: ["images"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteImages([id]),
    onSuccess: () => {
      toast.success("Image supprimée");
      qc.invalidateQueries({ queryKey: ["images"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
      navigate("/?scope=mine");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const reindex = useMutation({
    mutationFn: () => api.reindex(id),
    onSuccess: (r) => {
      if (r.indexed) toast.success("Image indexée : elle peut maintenant servir à la recherche");
      r.warnings.forEach((w) => toast.warning(w));
      qc.invalidateQueries({ queryKey: ["image", id] });
    },
  });

  if (q.isPending)
    return (
      <div className="flex justify-center py-32">
        <Spinner />
      </div>
    );
  if (!image)
    return (
      <div className="p-8">
        <EmptyState icon={<Search className="size-6" />} title="Image introuvable">
          Elle a peut-être été supprimée. <Link to="/">Retour à la galerie</Link>
        </EmptyState>
      </div>
    );

  const dirty = name !== image.filename || cat !== image.category_id;

  return (
    <div className="flex flex-col gap-6 px-8 pt-7 pb-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          <nav aria-label="Fil d'Ariane" className="text-[13px] text-muted">
            <Link to="/" className="text-muted no-underline hover:text-ink">
              Galerie
            </Link>
            {image.category_path.map((c) => (
              <span key={c.id}>
                {" / "}
                <Link to={`/?cat=${c.id}`} className="text-muted no-underline hover:text-ink">
                  {c.name}
                </Link>
              </span>
            ))}
          </nav>
          <h1 className="m-0 truncate font-display text-[30px] font-semibold tracking-[-0.02em]">{image.filename}</h1>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <a href={image.urls.download} className={buttonClass("secondary")}>
            <Download className="size-[18px]" aria-hidden />
            Télécharger
          </a>
          <Link to={`/images/${id}/transformer`} className={buttonClass("secondary")}>
            <Crop className="size-[18px]" aria-hidden />
            Transformer
          </Link>
          <Button icon={<Search className="size-[18px]" />} disabled={!image.indexed} onClick={() => navigate(`/recherche?image=${id}`)}>
            Images similaires
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-6">
        <section className="flex min-w-0 flex-[1_1_420px] flex-col gap-4">
          <div className="flex justify-center rounded-[18px] bg-ink p-4">
            <img src={image.urls.file} alt={image.filename} className="block max-h-[520px] w-full max-w-[640px] rounded-[10px] object-contain" />
          </div>
          <dl className="m-0 grid grid-cols-2 gap-px overflow-hidden rounded-[14px] border border-line bg-line">
            <Info label="Dimensions" value={`${image.width} × ${image.height} px`} />
            <Info label="Format" value={`${image.format} · ${formatBytes(image.size_bytes)}`} />
            <Info label="Origine" value={sourceLabel[image.source] + (image.public ? " · lecture seule" : "")} />
            <div className="bg-white px-4 py-3.5">
              <dt className="text-xs text-muted">Recherche</dt>
              <dd className="m-0 mt-1 flex items-center gap-2 text-[15px] font-semibold">
                <span className={`size-2 rounded-full ${image.indexed ? "bg-[#0e9f6e]" : "bg-accent"}`} />
                {image.indexed ? "Indexée" : "Non indexée"}
                {!image.indexed && image.mine && (
                  <Button size="sm" variant="secondary" loading={reindex.isPending} icon={<RefreshCw className="size-3.5" />} onClick={() => reindex.mutate()} className="ml-auto">
                    Indexer
                  </Button>
                )}
              </dd>
            </div>
          </dl>

          {image.transform && (
            <p className="m-0 text-sm text-muted">
              Créée par transformation de{" "}
              {image.parent_id ? <Link to={`/images/${image.parent_id}`}>l'image d'origine</Link> : "une image supprimée"} :{" "}
              {image.transform.map((o) => o.op).join(" → ")}
            </p>
          )}

          {image.mine && (
            <form
              className="flex flex-col gap-4 rounded-[18px] border border-line bg-white p-5"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <span className="text-[15px] font-semibold">Ranger et renommer</span>
              <Field label="Nom du fichier" htmlFor="img-name">
                <Input id="img-name" value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Field label="Catégorie" htmlFor="img-cat">
                <CategorySelect id="img-cat" value={cat} onChange={setCat} />
              </Field>
              <div className="flex flex-wrap justify-between gap-2.5">
                <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)}>
                  Supprimer
                </Button>
                <Button type="submit" disabled={!dirty} loading={save.isPending}>
                  Enregistrer
                </Button>
              </div>
            </form>
          )}
        </section>

        <DescriptorsPanel imageId={id} />
      </div>

      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Supprimer cette image ?"
        description="Le fichier est supprimé et l'image retirée de l'index de recherche. Cette action est définitive."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(false)}>
              Annuler
            </Button>
            <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>
              Supprimer définitivement
            </Button>
          </>
        }
      >
        {null}
      </Modal>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white px-4 py-3.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="m-0 mt-1 text-[15px] font-semibold">{value}</dd>
    </div>
  );
}

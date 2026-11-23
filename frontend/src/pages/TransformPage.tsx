/**
 * Transformer une image : on compose une liste d'opérations (recadrer, redimensionner, tourner...),
 * puis le backend crée une NOUVELLE image (l'originale n'est jamais modifiée).
 *
 * Le recadrage se dessine à la souris sur l'aperçu (quand c'est la 1re opération) ou se règle au pixel.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  Contrast,
  Crop,
  Droplet,
  FlipHorizontal2,
  Maximize2,
  Palette,
  RotateCw,
  Sun,
  X,
} from "lucide-react";
import { type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { Button, buttonClass, Field, IconButton, Input, Select, Spinner } from "@/components/ui";
import { CategorySelect } from "@/components/CategorySelect";
import { api, type Operation } from "@/lib/api";
import { cn } from "@/lib/utils";

type Size = { w: number; h: number };

const TOOLS: { op: Operation["op"]; label: string; icon: ReactNode }[] = [
  { op: "crop", label: "Recadrer", icon: <Crop className="size-5" /> },
  { op: "resize", label: "Taille", icon: <Maximize2 className="size-5" /> },
  { op: "rotate", label: "Rotation", icon: <RotateCw className="size-5" /> },
  { op: "flip", label: "Miroir", icon: <FlipHorizontal2 className="size-5" /> },
  { op: "grayscale", label: "Gris", icon: <Palette className="size-5" /> },
  { op: "brightness", label: "Lumière", icon: <Sun className="size-5" /> },
  { op: "contrast", label: "Contraste", icon: <Contrast className="size-5" /> },
  { op: "blur", label: "Flou", icon: <Droplet className="size-5" /> },
];

const LABELS: Record<Operation["op"], string> = {
  crop: "Recadrer",
  resize: "Redimensionner",
  rotate: "Rotation",
  flip: "Miroir",
  grayscale: "Niveaux de gris",
  brightness: "Luminosité",
  contrast: "Contraste",
  blur: "Flou",
};

/** Opération par défaut, adaptée à la taille actuelle de l'image. */
function defaultOp(op: Operation["op"], s: Size): Operation {
  switch (op) {
    case "crop":
      return { op, x: Math.round(s.w * 0.1), y: Math.round(s.h * 0.1), width: Math.round(s.w * 0.8), height: Math.round(s.h * 0.8) };
    case "resize":
      return { op, width: Math.round(s.w / 2) };
    case "rotate":
      return { op, angle: 90 };
    case "flip":
      return { op, direction: "horizontal" };
    case "grayscale":
      return { op };
    case "brightness":
      return { op, factor: 1.3 };
    case "contrast":
      return { op, factor: 1.3 };
    case "blur":
      return { op, radius: 2 };
  }
}

/** Taille après une opération (mêmes règles que le backend Pillow). */
function sizeAfter(o: Operation, s: Size): Size {
  if (o.op === "crop") return { w: o.width, h: o.height };
  if (o.op === "resize") {
    if (o.width && o.height) return { w: o.width, h: o.height };
    if (o.width) return { w: o.width, h: Math.max(1, Math.round((s.h * o.width) / s.w)) };
    if (o.height) return { w: Math.max(1, Math.round((s.w * o.height) / s.h)), h: o.height };
    return s;
  }
  if (o.op === "rotate") {
    const a = (o.angle * Math.PI) / 180;
    return {
      w: Math.round(Math.abs(s.w * Math.cos(a)) + Math.abs(s.h * Math.sin(a))),
      h: Math.round(Math.abs(s.w * Math.sin(a)) + Math.abs(s.h * Math.cos(a))),
    };
  }
  return s;
}

export function TransformPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["image", id], queryFn: () => api.image(id).then((r) => r.image) });
  const image = q.data;

  const [ops, setOps] = useState<Operation[]>([]);
  const [selected, setSelected] = useState(0);
  const [filename, setFilename] = useState("");
  const [category, setCategory] = useState<number | null>(null);

  useEffect(() => {
    if (image) {
      const stem = image.filename.replace(/\.[^.]+$/, "");
      setFilename(`${stem}_transform.${image.format === "PNG" ? "png" : "jpg"}`);
      setCategory(image.category_id); // par défaut : la même catégorie que l'image d'origine (ex. yacht)
      setOps([defaultOp("crop", { w: image.width, h: image.height })]);
    }
  }, [image]);

  // Taille avant chaque opération : nécessaire pour valider et pour les valeurs par défaut
  const sizes = useMemo(() => {
    if (!image) return [] as Size[];
    const out: Size[] = [{ w: image.width, h: image.height }];
    ops.forEach((o) => out.push(sizeAfter(o, out[out.length - 1])));
    return out;
  }, [ops, image]);
  const finalSize = sizes[sizes.length - 1];

  const create = useMutation({
    mutationFn: () => api.transform(id, ops, filename, category),
    onSuccess: (r) => {
      toast.success(`Nouvelle image « ${r.image.filename} » créée`);
      r.warnings.forEach((w) => toast.warning(w));
      qc.invalidateQueries({ queryKey: ["images"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
      navigate(`/images/${r.image.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!image)
    return (
      <div className="flex justify-center py-32">
        <Spinner />
      </div>
    );

  const updateOp = (i: number, patch: Partial<Operation>) =>
    setOps((list) => list.map((o, j) => (j === i ? ({ ...o, ...patch } as Operation) : o)));
  const addOp = (op: Operation["op"]) => {
    setOps((list) => [...list, defaultOp(op, finalSize)]);
    setSelected(ops.length);
  };
  const removeOp = (i: number) => {
    setOps((list) => list.filter((_, j) => j !== i));
    setSelected(0);
  };

  const firstCrop = ops[0]?.op === "crop" ? ops[0] : null;

  return (
    <>
      <header className="flex flex-wrap items-center gap-4 border-b border-line bg-white px-8 py-4">
        <Link to={`/images/${id}`} aria-label="Retour à l'image" className="flex size-10 items-center justify-center rounded-[10px] border border-line-strong text-ink">
          <ArrowLeft className="size-[18px]" />
        </Link>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h1 className="m-0 truncate font-display text-[22px] font-semibold">Transformer {image.filename}</h1>
          <span className="text-[13px] text-muted">Une nouvelle image sera créée ; l'originale reste intacte.</span>
        </div>
        <div className="ml-auto flex gap-2.5">
          <Link to={`/images/${id}`} className={buttonClass("secondary")}>
            Annuler
          </Link>
          <Button icon={<Check className="size-[18px]" strokeWidth={2.4} />} loading={create.isPending} disabled={!ops.length || !filename.trim()} onClick={() => create.mutate()}>
            Créer la nouvelle image
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-start gap-6 px-8 py-7">
        <section aria-label="Aperçu" className="flex min-w-0 flex-[1_1_520px] flex-col gap-3.5">
          <div className="grid gap-5 rounded-[18px] bg-ink p-5 sm:grid-cols-2 sm:p-6">
            <figure className="m-0 flex flex-col gap-2.5">
              <figcaption className="text-xs font-semibold tracking-[0.06em] text-side-muted uppercase">
                Original · {image.width} × {image.height}
              </figcaption>
              <div className="flex flex-1 items-center justify-center">
                <CropPreview
                  src={image.urls.file}
                  size={{ w: image.width, h: image.height }}
                  crop={firstCrop}
                  onCrop={(c) => {
                    updateOp(0, c);
                    setSelected(0);
                  }}
                />
              </div>
            </figure>
            <figure className="m-0 flex flex-col gap-2.5">
              <figcaption className="text-xs font-semibold tracking-[0.06em] text-side-muted uppercase">
                Résultat · {finalSize.w} × {finalSize.h}
              </figcaption>
              <div className="flex flex-1 items-center justify-center">
                <ResultPreview src={image.urls.file} ops={ops} />
              </div>
            </figure>
          </div>
          <p className="m-0 text-sm text-muted">
            {firstCrop ? "Glissez sur l'original pour dessiner le recadrage. " : ""}
            L'aperçu du résultat se met à jour à chaque réglage ; l'image finale est calculée par le serveur.
          </p>
        </section>

        <section aria-label="Opérations" className="flex min-w-[300px] flex-[0_1_380px] flex-col gap-4">
          <div className="flex flex-col gap-3.5 rounded-[18px] border border-line bg-white p-5">
            <span className="text-[15px] font-semibold">Ajouter une opération</span>
            <div className="grid grid-cols-4 gap-2">
              {TOOLS.map((t) => (
                <button
                  key={t.op}
                  type="button"
                  onClick={() => addOp(t.op)}
                  className="flex h-16 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-line bg-white text-ink hover:border-primary hover:bg-primary-soft hover:text-primary-hover"
                >
                  {t.icon}
                  <span className="text-[11px] font-semibold">{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-[18px] border border-line bg-white p-5">
            <div className="flex items-baseline justify-between">
              <span className="text-[15px] font-semibold">Étapes appliquées</span>
              <span className="text-xs text-muted">dans l'ordre</span>
            </div>
            {ops.length === 0 && <p className="m-0 text-sm text-muted">Ajoutez au moins une opération.</p>}
            {ops.map((o, i) => (
              <div
                key={i}
                className={cn("flex flex-col gap-2.5 rounded-xl px-3.5 py-3", selected === i ? "border-2 border-primary bg-[#f7f7ff]" : "border border-line")}
                onFocusCapture={() => setSelected(i)}
              >
                <div className="flex items-center justify-between">
                  <button type="button" onClick={() => setSelected(i)} className="cursor-pointer border-0 bg-transparent p-0 text-left text-sm font-semibold">
                    {i + 1} · {LABELS[o.op]}
                  </button>
                  <IconButton label={`Retirer l'étape ${LABELS[o.op]}`} onClick={() => removeOp(i)} className="size-7">
                    <X className="size-4" />
                  </IconButton>
                </div>
                <OpEditor op={o} before={sizes[i]} onChange={(p) => updateOp(i, p)} />
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-3 rounded-[18px] border border-line bg-white p-5">
            <Field label="Nom de la nouvelle image" htmlFor="tr-name">
              <Input id="tr-name" value={filename} onChange={(e) => setFilename(e.target.value)} />
            </Field>
            <Field label="Ranger dans" htmlFor="tr-cat">
              <CategorySelect id="tr-cat" value={category} onChange={setCategory} />
            </Field>
          </div>
        </section>
      </div>
    </>
  );
}

/** Champs d'une opération. `before` = taille de l'image avant cette étape (bornes du recadrage). */
function OpEditor({ op, before, onChange }: { op: Operation; before: Size; onChange: (p: Partial<Operation>) => void }) {
  const n = (v: string) => (v === "" ? undefined : Number(v));
  const small = "h-[34px] rounded-lg px-2 text-sm";
  const lbl = "flex flex-col gap-1 text-[11px] font-semibold text-muted";
  switch (op.op) {
    case "crop":
      return (
        <div className="grid grid-cols-4 gap-2">
          {(["x", "y", "width", "height"] as const).map((k) => (
            <label key={k} className={lbl}>
              {{ x: "x", y: "y", width: "largeur", height: "hauteur" }[k]}
              <Input type="number" min={k === "width" || k === "height" ? 1 : 0} max={k === "x" || k === "width" ? before.w : before.h} value={op[k]} onChange={(e) => onChange({ [k]: n(e.target.value) ?? 0 })} className={small} />
            </label>
          ))}
        </div>
      );
    case "resize":
      return (
        <div className="grid grid-cols-2 gap-2">
          <label className={lbl}>
            largeur
            <Input type="number" min={1} value={op.width ?? ""} placeholder="auto" onChange={(e) => onChange({ width: n(e.target.value) })} className={small} />
          </label>
          <label className={lbl}>
            hauteur
            <Input type="number" min={1} value={op.height ?? ""} placeholder="auto" onChange={(e) => onChange({ height: n(e.target.value) })} className={small} />
          </label>
          <span className="col-span-2 text-xs text-muted">Une seule dimension : l'autre garde les proportions.</span>
        </div>
      );
    case "rotate":
      return <Slider label="Angle" value={op.angle} min={-180} max={180} step={1} unit="°" onChange={(v) => onChange({ angle: v })} />;
    case "flip":
      return (
        <Select value={op.direction} onChange={(e) => onChange({ direction: e.target.value as "horizontal" | "vertical" })} className={small}>
          <option value="horizontal">Horizontal (gauche ↔ droite)</option>
          <option value="vertical">Vertical (haut ↕ bas)</option>
        </Select>
      );
    case "grayscale":
      return <span className="text-xs text-muted">Aucun réglage.</span>;
    case "brightness":
    case "contrast":
      return <Slider label="Facteur (1 = inchangé)" value={op.factor} min={0} max={3} step={0.05} onChange={(v) => onChange({ factor: v })} />;
    case "blur":
      return <Slider label="Rayon" value={op.radius} min={0} max={20} step={0.5} unit=" px" onChange={(v) => onChange({ radius: v })} />;
  }
}

function Slider({ label, value, min, max, step, unit = "", onChange }: { label: string; value: number; min: number; max: number; step: number; unit?: string; onChange: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-1.5 text-[13px]">
      <span className="flex justify-between">
        <span className="text-muted">{label}</span>
        <span className="font-semibold tabular-nums">
          {String(value).replace(".", ",")}
          {unit}
        </span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full" />
    </label>
  );
}

/**
 * Applique les opérations dans le navigateur avec un <canvas> pour un aperçu immédiat.
 * Mêmes opérations, dans le même ordre, que Pillow côté serveur :
 *   crop / resize / rotate / flip -> dessin géométrique ; filtres -> ctx.filter (comme en CSS).
 */
function renderOps(img: HTMLImageElement, ops: Operation[]): HTMLCanvasElement {
  let canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  canvas.getContext("2d")!.drawImage(img, 0, 0);

  // Prépare une nouvelle toile de taille w x h et y dessine l'étape suivante
  const next = (w: number, h: number, draw: (ctx: CanvasRenderingContext2D, src: HTMLCanvasElement) => void) => {
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w));
    c.height = Math.max(1, Math.round(h));
    draw(c.getContext("2d")!, canvas);
    canvas = c;
  };

  for (const o of ops) {
    const W = canvas.width;
    const H = canvas.height;
    switch (o.op) {
      case "crop": {
        const x = Math.max(0, Math.min(o.x, W - 1));
        const y = Math.max(0, Math.min(o.y, H - 1));
        const w = Math.max(1, Math.min(o.width, W - x));
        const h = Math.max(1, Math.min(o.height, H - y));
        next(w, h, (ctx, src) => ctx.drawImage(src, x, y, w, h, 0, 0, w, h));
        break;
      }
      case "resize": {
        const s = sizeAfter(o, { w: W, h: H });
        next(s.w, s.h, (ctx, src) => {
          ctx.imageSmoothingQuality = "high";
          ctx.drawImage(src, 0, 0, s.w, s.h);
        });
        break;
      }
      case "rotate": {
        const s = sizeAfter(o, { w: W, h: H });
        next(s.w, s.h, (ctx, src) => {
          ctx.fillStyle = "#ffffff"; // Pillow remplit les coins en blanc (fillcolor)
          ctx.fillRect(0, 0, s.w, s.h);
          ctx.translate(s.w / 2, s.h / 2);
          ctx.rotate((-o.angle * Math.PI) / 180); // Pillow : sens inverse des aiguilles d'une montre
          ctx.drawImage(src, -W / 2, -H / 2);
        });
        break;
      }
      case "flip":
        next(W, H, (ctx, src) => {
          if (o.direction === "horizontal") {
            ctx.translate(W, 0);
            ctx.scale(-1, 1);
          } else {
            ctx.translate(0, H);
            ctx.scale(1, -1);
          }
          ctx.drawImage(src, 0, 0);
        });
        break;
      default: {
        const filter =
          o.op === "grayscale" ? "grayscale(1)" : o.op === "brightness" ? `brightness(${o.factor})` : o.op === "contrast" ? `contrast(${o.factor})` : `blur(${o.radius}px)`;
        next(W, H, (ctx, src) => {
          ctx.filter = filter;
          ctx.drawImage(src, 0, 0);
        });
      }
    }
  }
  return canvas;
}

function ResultPreview({ src, ops }: { src: string; ops: Operation[] }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const im = new window.Image();
    im.onload = () => setImg(im);
    im.src = src; // même origine (/api) : la toile n'est pas « contaminée », on peut la lire
  }, [src]);

  useEffect(() => {
    if (!img) return;
    // petite attente : on ne recalcule pas à chaque pixel quand on fait glisser un curseur
    const t = setTimeout(() => {
      try {
        setUrl(renderOps(img, ops).toDataURL("image/jpeg", 0.9));
      } catch {
        setUrl(null);
      }
    }, 80);
    return () => clearTimeout(t);
  }, [img, ops]);

  if (!url) return <Spinner className="text-side-muted" />;
  return <img src={url} alt="Aperçu du résultat" className="block max-h-[420px] max-w-full rounded-md object-contain" />;
}

/** Aperçu avec cadre de recadrage : on dessine un rectangle à la souris (ou au doigt). */
function CropPreview({ src, size, crop, onCrop }: { src: string; size: Size; crop: Extract<Operation, { op: "crop" }> | null; onCrop: (c: Partial<Operation>) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  // coordonnées de la souris -> pixels de l'image d'origine
  const toImage = (e: ReactPointerEvent) => {
    const r = box.current!.getBoundingClientRect();
    return {
      x: Math.round(Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1) * size.w),
      y: Math.round(Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1) * size.h),
    };
  };
  const onDown = (e: ReactPointerEvent) => {
    if (!crop) return;
    box.current!.setPointerCapture(e.pointerId);
    start.current = toImage(e);
  };
  const onMove = (e: ReactPointerEvent) => {
    if (!start.current) return;
    const p = toImage(e);
    const x = Math.min(start.current.x, p.x);
    const y = Math.min(start.current.y, p.y);
    onCrop({ x, y, width: Math.max(1, Math.abs(p.x - start.current.x)), height: Math.max(1, Math.abs(p.y - start.current.y)) });
  };

  return (
    <div
      ref={box}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={() => (start.current = null)}
      className={cn("relative w-full max-w-[640px] touch-none overflow-hidden rounded-md select-none", crop && "cursor-crosshair")}
      style={{ aspectRatio: `${size.w} / ${size.h}` }}
    >
      <img src={src} alt="Image à transformer" draggable={false} className="block size-full object-cover" />
      {crop && (
        <div
          className="pointer-events-none absolute box-border border-2 border-white shadow-[0_0_0_9999px_rgba(14,21,37,.6)]"
          style={{
            left: `${(crop.x / size.w) * 100}%`,
            top: `${(crop.y / size.h) * 100}%`,
            width: `${(crop.width / size.w) * 100}%`,
            height: `${(crop.height / size.h) * 100}%`,
          }}
        >
          <div className="grid size-full grid-cols-3 grid-rows-3">
            {Array.from({ length: 9 }, (_, i) => (
              <div key={i} className={cn(i % 3 !== 2 && "border-r", i < 6 && "border-b", "border-white/45")} />
            ))}
          </div>
          <span className="absolute top-2 left-2 rounded-md bg-ink/80 px-2 py-0.5 text-xs font-semibold text-white">
            {crop.width} × {crop.height}
          </span>
        </div>
      )}
    </div>
  );
}

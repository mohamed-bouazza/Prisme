/**
 * Recherche par le contenu (Tâche 2).
 *
 * Requête = une image de la galerie (?image=12) OU un fichier envoyé (non enregistré).
 *
 * Retour de pertinence FRE (étape 7) : l'utilisateur marque les résultats « pertinente » /
 * « non pertinente », puis relance. Les marquages s'ACCUMULENT d'une itération à l'autre et sont
 * tous renvoyés au serveur (qui ne garde aucune session) ; les non pertinentes ne reviennent plus.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ImageUp, RefreshCw, RotateCcw, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { Badge, Button, EmptyState, Field, Select, Spinner } from "@/components/ui";
import { api, type FeedbackResponse, type SearchResult } from "@/lib/api";
import { useCategories } from "@/lib/hooks";
import { cn, num } from "@/lib/utils";

type Mark = "rel" | "non";
type Mode = "balanced" | "color" | "texture";

const DESCRIPTORS = [
  ["color_hist", "Histogramme HSV", "color"],
  ["color_moments", "Moments de couleur", "color"],
  ["dominant_colors", "Couleurs dominantes", "color"],
  ["glcm", "Texture GLCM", "texture"],
  ["lbp", "Texture LBP", "texture"],
] as const;

/** Poids envoyés à l'API selon le mode choisi (undefined = tous égaux). */
function modeWeights(mode: Mode): Record<string, number> | undefined {
  if (mode === "balanced") return undefined;
  return Object.fromEntries(DESCRIPTORS.filter((d) => d[2] === mode).map((d) => [d[0], 1]));
}

export function SearchPage() {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const imageId = Number(params.get("image")) || null;
  const file = (location.state as { file?: File } | null)?.file ?? null;
  const [k, setK] = useState(20);
  const [mode, setMode] = useState<Mode>("balanced");
  const [marks, setMarks] = useState<Record<number, Mark>>({});
  const { data: categories = [] } = useCategories();
  const catName = useMemo(() => new Map(categories.map((c) => [c.id, c.name])), [categories]);

  const fileUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  const queryImage = useQuery({
    queryKey: ["image", imageId],
    queryFn: () => api.image(imageId!).then((r) => r.image),
    enabled: imageId !== null,
  });

  const search = useQuery({
    queryKey: ["search", imageId, file?.name, file?.size, k, mode],
    queryFn: () => (imageId ? api.searchById(imageId, k, modeWeights(mode)) : api.searchByFile(file!, k, modeWeights(mode))),
    enabled: imageId !== null || file !== null,
    staleTime: 60_000,
  });

  // --------------------------------------------------------- session de retour de pertinence
  // feedback = réponse de la dernière relance (null = itération 1, recherche simple)
  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null);
  // historique : précision jugée par l'utilisateur sur chaque page déjà relancée
  const [history, setHistory] = useState<{ iteration: number; rel: number; shown: number }[]>([]);
  const resetSession = () => {
    setMarks({});
    setFeedback(null);
    setHistory([]);
  };
  // nouvelle requête ou nouveaux réglages -> nouvelle session
  useEffect(resetSession, [imageId, file, k, mode]);

  const results: SearchResult[] = feedback?.results ?? search.data?.results ?? [];
  const iteration = history.length + 1;
  const nRel = results.filter((r) => marks[r.image.id] === "rel").length;
  const nNon = results.filter((r) => marks[r.image.id] === "non").length;
  const totalRel = Object.values(marks).filter((m) => m === "rel").length;
  const totalNon = Object.values(marks).filter((m) => m === "non").length;
  const precision = results.length ? nRel / results.length : 0;
  const toggle = (id: number, m: Mark) =>
    setMarks((s) => {
      const n = { ...s };
      if (n[id] === m) delete n[id];
      else n[id] = m;
      return n;
    });

  const relaunch = useMutation({
    mutationFn: () => {
      const rel = Object.keys(marks).filter((id) => marks[Number(id)] === "rel").map(Number);
      const non = Object.keys(marks).filter((id) => marks[Number(id)] === "non").map(Number);
      return api.feedback(imageId ? { imageId } : { file: file! }, rel, non, k);
    },
    onSuccess: (r) => {
      setHistory((h) => [...h, { iteration, rel: nRel, shown: results.length }]);
      setFeedback(r);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ------------------------------------------------------------- aucune requête choisie
  if (!imageId && !file) {
    return (
      <div className="flex flex-col gap-6 px-8 pt-7 pb-12">
        <h1 className="m-0 font-display text-[30px] font-semibold tracking-[-0.02em]">Recherche par le contenu</h1>
        <EmptyState icon={<Search className="size-6" />} title="Choisissez une image requête">
          <p className="mt-0">
            Ouvrez une image de la <Link to="/">galerie</Link> et cliquez sur « Images similaires », ou envoyez une image depuis votre ordinateur.
          </p>
          <label className="mt-2 inline-flex h-11 cursor-pointer items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover">
            <ImageUp className="size-[18px]" aria-hidden />
            Envoyer une image
            <input
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) navigate("/recherche", { state: { file: f } });
              }}
            />
          </label>
        </EmptyState>
      </div>
    );
  }

  const weights = modeWeights(mode);
  const active = DESCRIPTORS.filter((d) => !weights || weights[d[0]]);

  return (
    <div className="flex flex-wrap content-start gap-6 px-8 pt-7 pb-12">
      <section aria-label="Requête et session" className="flex min-w-[280px] flex-[0_1_320px] flex-col gap-4">
        <div className="flex flex-col gap-3.5 rounded-[18px] border border-line bg-white p-4">
          <span className="text-xs font-semibold tracking-[0.06em] text-muted uppercase">Image requête</span>
          <img
            src={imageId ? queryImage.data?.urls.file : fileUrl ?? undefined}
            alt="Image requête"
            className="block aspect-[4/3] w-full rounded-xl bg-[#eef0f5] object-cover"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-semibold">{imageId ? queryImage.data?.filename : file?.name}</span>
            {imageId && queryImage.data?.category_path.length ? (
              <Badge>{queryImage.data.category_path[queryImage.data.category_path.length - 1].name}</Badge>
            ) : (
              <Badge tone="muted">{imageId ? "galerie" : "fichier envoyé"}</Badge>
            )}
          </div>
          <Field label="Combinaison des descripteurs" htmlFor="mode">
            <Select id="mode" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              <option value="balanced">Équilibrée (5 descripteurs)</option>
              <option value="color">Couleur seule</option>
              <option value="texture">Texture seule</option>
            </Select>
          </Field>
          <Field label="Nombre de résultats" htmlFor="k">
            <Select id="k" value={k} onChange={(e) => setK(Number(e.target.value))}>
              {[10, 20, 40, 60, 100].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="flex flex-col gap-4 rounded-[18px] bg-ink p-5 text-[#e6e9f0]">
          <div className="flex items-baseline justify-between">
            <span className="font-display text-lg font-semibold text-white">Itération {iteration}</span>
            <span className="text-xs text-[#9aa3b5]">{feedback ? "retour de pertinence FRE" : "recherche simple"}</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <div className="rounded-xl bg-ink-2 p-3">
              <div className="font-display text-[26px] font-semibold text-primary-light">{nRel}</div>
              <div className="text-xs text-[#b7bfce]">pertinentes</div>
            </div>
            <div className="rounded-xl bg-ink-2 p-3">
              <div className="font-display text-[26px] font-semibold text-[#fdba74]">{nNon}</div>
              <div className="text-xs text-[#b7bfce]">non pertinentes</div>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-[13px]">
              <span className="text-[#b7bfce]">Précision de cette page</span>
              <span className="font-semibold text-white">{Math.round(precision * 100)} %</span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-ink-2">
              <div className="h-full rounded bg-primary-light transition-[width]" style={{ width: `${precision * 100}%` }} />
            </div>
          </div>
          <Button
            size="lg"
            loading={relaunch.isPending}
            disabled={!results.length || (!imageId && totalRel === 0) || (totalRel === 0 && totalNon === 0)}
            title={totalRel + totalNon === 0 ? "Marquez au moins un résultat" : undefined}
            icon={<RefreshCw className="size-[18px]" />}
            onClick={() => relaunch.mutate()}
          >
            Relancer avec mes choix
          </Button>
          <p className="m-0 -mt-2 text-center text-xs text-[#9aa3b5]">
            Cumul : {totalRel} pertinente(s), {totalNon} non pertinente(s)
          </p>

          {history.length > 0 && (
            <ol className="m-0 flex list-none flex-col gap-2 border-t border-[#2a3348] p-0 pt-3">
              {[...history, { iteration, rel: nRel, shown: results.length }].map((h) => (
                <li key={h.iteration} className="flex items-center gap-3 text-[13px]">
                  <span className="w-[74px] shrink-0 text-[#b7bfce]">Itération {h.iteration}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded bg-ink-2">
                    <div className="h-full rounded bg-primary-light" style={{ width: `${h.shown ? (100 * h.rel) / h.shown : 0}%` }} />
                  </div>
                  <span className="w-10 text-right font-semibold text-white tabular-nums">{h.shown ? Math.round((100 * h.rel) / h.shown) : 0} %</span>
                </li>
              ))}
            </ol>
          )}

          <button
            type="button"
            onClick={resetSession}
            className="flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-[#2a3348] bg-transparent text-sm font-medium text-side-text hover:text-white"
          >
            <RotateCcw className="size-4" aria-hidden />
            Recommencer la session
          </button>
        </div>

        <div className="flex flex-col gap-3 rounded-[18px] border border-line bg-white p-5">
          <div className="flex items-baseline justify-between">
            <span className="text-[15px] font-semibold">Poids des descripteurs</span>
            {feedback && <span className="text-xs text-muted">appris par FRE</span>}
          </div>
          {DESCRIPTORS.map(([key, label]) => {
            const w = feedback ? (feedback.desc_weights[key] ?? 0) : active.some((a) => a[0] === key) ? 1 / active.length : 0;
            return (
              <div key={key} className="flex flex-col gap-1.5">
                <div className="flex justify-between text-[13px]">
                  <span className={w ? "" : "text-muted"}>{label}</span>
                  <span className="font-semibold">{Math.round(w * 100)} %</span>
                </div>
                <div className="h-1.5 rounded-full bg-[#eef0f5]">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${w * 100}%` }} />
                </div>
              </div>
            );
          })}
          <p className="m-0 text-xs leading-normal text-muted">
            {feedback
              ? `Calculés à partir de vos ${feedback.n_relevant} exemples pertinents (requête comprise) et ${feedback.n_nonrelevant} non pertinents : un descripteur pèse plus s'il classe bien vos images pertinentes avant les autres. À l'intérieur de chaque descripteur, les composantes sur lesquelles vos images pertinentes se ressemblent pèsent aussi davantage.`
              : "À l'itération 1, chaque descripteur actif compte autant. Après la relance, FRE renforce ceux sur lesquels vos images pertinentes se ressemblent."}
          </p>
        </div>
      </section>

      <section aria-labelledby="res-title" className="flex min-w-0 flex-[1_1_560px] flex-col gap-[18px]">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <h1 id="res-title" className="m-0 font-display text-[30px] font-semibold tracking-[-0.02em]">
              {search.data ? `${results.length} images les plus proches` : "Recherche…"}
            </h1>
            <p className="m-0 text-sm text-muted">
              {feedback
                ? "Résultats recalculés avec vos marquages. Les images non pertinentes ne reviennent plus ; continuez à marquer puis relancez."
                : "Marquez chaque résultat, puis relancez : la recherche s'ajustera à vos choix."}
              {(feedback?.cbir_ms ?? search.data?.cbir_ms) != null &&
                ` Calculé en ${Math.round((feedback?.cbir_ms ?? search.data?.cbir_ms)!)} ms sur toute la base.`}
            </p>
          </div>
          <div className="flex gap-3.5 text-[13px] text-muted">
            <span className="flex items-center gap-1.5">
              <span className="size-3 rounded bg-primary" />
              Pertinente
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-3 rounded bg-reject" />
              Non pertinente
            </span>
          </div>
        </div>

        {search.isPending ? (
          <div className="flex justify-center py-24">
            <Spinner />
          </div>
        ) : search.isError ? (
          <EmptyState icon={<X className="size-6" />} title="La recherche a échoué">
            {(search.error as Error).message}
          </EmptyState>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-4">
            {results.map((r) => {
              const m = marks[r.image.id];
              return (
                <article
                  key={r.image.id}
                  className={cn(
                    "overflow-hidden rounded-[14px] bg-white",
                    m === "rel" && "border-2 border-primary shadow-[0_0_0_4px_rgba(67,56,202,.14)]",
                    m === "non" && "border-2 border-reject shadow-[0_0_0_4px_rgba(194,65,12,.12)]",
                    !m && "border border-line",
                  )}
                >
                  <Link to={`/images/${r.image.id}`} className="relative block" aria-label={`Ouvrir ${r.image.filename}`}>
                    <img src={r.image.urls.thumb} alt={r.image.filename} loading="lazy" className="block aspect-[4/3] w-full bg-[#eef0f5] object-cover" />
                    <span className="absolute top-2 left-2 flex h-[26px] min-w-[26px] items-center justify-center rounded-lg bg-ink/80 px-2 text-xs font-bold text-white">
                      {r.rank}
                    </span>
                  </Link>
                  <div className="flex flex-col gap-2.5 px-3 pt-2.5 pb-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-[13px] font-semibold">{r.image.category_id ? catName.get(r.image.category_id) : r.image.filename}</span>
                      <span className="shrink-0 text-xs text-muted tabular-nums">d = {num(r.distance)}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        aria-pressed={m === "rel"}
                        aria-label={`${r.image.filename} : pertinente`}
                        onClick={() => toggle(r.image.id, "rel")}
                        className={cn(
                          "flex h-9 cursor-pointer items-center justify-center rounded-[9px]",
                          m === "rel" ? "bg-primary text-white" : "border border-line-strong bg-white text-primary-hover hover:bg-primary-soft",
                        )}
                      >
                        <Check className="size-4" strokeWidth={2.6} />
                      </button>
                      <button
                        type="button"
                        aria-pressed={m === "non"}
                        aria-label={`${r.image.filename} : non pertinente`}
                        onClick={() => toggle(r.image.id, "non")}
                        className={cn(
                          "flex h-9 cursor-pointer items-center justify-center rounded-[9px]",
                          m === "non" ? "bg-reject text-white" : "border border-line-strong bg-white text-reject-ink hover:bg-reject-soft",
                        )}
                      >
                        <X className="size-4" strokeWidth={2.6} />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

/**
 * Affichage des descripteurs d'une image (Tâche 1) :
 *   Couleur : histogramme HSV (regroupé par teinte), couleurs dominantes, moments de couleur
 *   Texture : propriétés GLCM, histogramme LBP
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Segmented, Spinner } from "@/components/ui";
import { api, type Descriptors } from "@/lib/api";
import { num, pct } from "@/lib/utils";

export function DescriptorsPanel({ imageId }: { imageId: number }) {
  const [tab, setTab] = useState<"color" | "texture">("color");
  const q = useQuery({
    queryKey: ["descriptors", imageId],
    queryFn: () => api.descriptors(imageId),
    staleTime: Infinity, // les descripteurs d'une image ne changent jamais
    retry: false,
  });

  return (
    <section aria-labelledby="desc-title" className="flex min-w-0 flex-[1.3_1_520px] flex-col gap-7 rounded-[18px] border border-line bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="desc-title" className="m-0 font-display text-[22px] font-semibold">
          Descripteurs
        </h2>
        <Segmented
          label="Type de descripteur"
          value={tab}
          onChange={setTab}
          options={[
            { value: "color", label: "Couleur" },
            { value: "texture", label: "Texture" },
          ]}
        />
      </div>
      {q.isPending ? (
        <div className="flex flex-col items-center gap-3 py-16 text-sm text-muted">
          <Spinner />
          Calcul des descripteurs par le moteur CBIR…
        </div>
      ) : q.isError ? (
        <p role="alert" className="m-0 rounded-xl bg-reject-soft px-4 py-3 text-sm font-medium text-reject-ink">
          {(q.error as Error).message}
        </p>
      ) : tab === "color" ? (
        <ColorTab d={q.data.descriptors} />
      ) : (
        <TextureTab d={q.data.descriptors} />
      )}
    </section>
  );
}

function SectionTitle({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h3 className="m-0 text-[15px] font-semibold">{title}</h3>
      <span className="text-xs text-muted">{hint}</span>
    </div>
  );
}

function ColorTab({ d }: { d: Descriptors }) {
  // Histogramme 8 x 4 x 4 (teinte x saturation x valeur) -> somme sur S et V : une barre par teinte
  const [nh, ns, nv] = d.color_histogram.bins;
  const hues = Array.from({ length: nh }, (_, h) => {
    let s = 0;
    for (let i = 0; i < ns * nv; i++) s += d.color_histogram.values[h * ns * nv + i];
    return s;
  });
  const maxHue = Math.max(...hues, 1e-9);
  const hueDeg = (h: number) => Math.round(((h + 0.5) * 360) / nh); // centre de la case, en degrés

  return (
    <>
      <div className="flex flex-col gap-3">
        <SectionTitle title="Histogramme HSV" hint={`${nh * ns * nv} cases regroupées par teinte`} />
        <div className="grid h-[170px] items-end gap-2.5 border-b border-line px-1" style={{ gridTemplateColumns: `repeat(${nh}, minmax(0, 1fr))` }}>
          {hues.map((v, h) => (
            <div key={h} className="flex h-full flex-col items-center justify-end gap-1.5">
              <span className="text-[11px] text-muted">{pct(v)}</span>
              <div
                className="w-full max-w-11 rounded-t-md rounded-b-sm"
                style={{ height: Math.max(3, (v / maxHue) * 120), background: `hsl(${hueDeg(h)}, 70%, 50%)` }}
                title={`Teinte ${hueDeg(h)}° : ${pct(v)} des pixels`}
              />
            </div>
          ))}
        </div>
        <div className="grid gap-2.5 px-1" style={{ gridTemplateColumns: `repeat(${nh}, minmax(0, 1fr))` }}>
          {hues.map((_, h) => (
            <span key={h} className="text-center text-[11px] text-muted">
              {hueDeg(h)}°
            </span>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <SectionTitle title="Couleurs dominantes" hint={`K-means, k = ${d.dominant_colors.length}`} />
        <div className="flex h-[18px] overflow-hidden rounded-full">
          {d.dominant_colors.map((c) => (
            <div key={c.hex + c.proportion} style={{ width: `${c.proportion * 100}%`, background: c.hex }} />
          ))}
        </div>
        <div className="grid gap-2.5" style={{ gridTemplateColumns: `repeat(${d.dominant_colors.length}, minmax(0, 1fr))` }}>
          {d.dominant_colors.map((c) => (
            <div key={c.hex + c.proportion} className="flex min-w-0 flex-col gap-1.5">
              <div className="h-12 rounded-[10px] border border-ink/10" style={{ background: c.hex }} />
              <span className="font-mono text-[13px] font-semibold">{c.hex}</span>
              <span className="text-xs text-muted">{pct(c.proportion)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="m-0 text-[15px] font-semibold">Moments de couleur</h3>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm tabular-nums">
            <thead>
              <tr className="text-right text-xs text-muted">
                <th scope="col" className="py-2 text-left font-semibold">Canal</th>
                <th scope="col" className="py-2 font-semibold">Moyenne</th>
                <th scope="col" className="py-2 font-semibold">Écart-type</th>
                <th scope="col" className="py-2 font-semibold">Asymétrie</th>
              </tr>
            </thead>
            <tbody className="text-right">
              {(["H", "S", "V"] as const).map((ch) => (
                <tr key={ch} className="border-t border-[#eef0f5]">
                  <th scope="row" className="py-2.5 text-left font-medium">
                    {{ H: "Teinte (H)", S: "Saturation (S)", V: "Valeur (V)" }[ch]}
                  </th>
                  <td>{num(d.color_moments[ch].mean, 2)}</td>
                  <td>{num(d.color_moments[ch].std, 2)}</td>
                  <td>{num(d.color_moments[ch].skewness, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

const GLCM_LABELS: Record<string, [string, number]> = {
  contrast: ["Contraste", 20],
  dissimilarity: ["Dissimilarité", 5],
  homogeneity: ["Homogénéité", 1],
  energy: ["Énergie", 1],
  correlation: ["Corrélation", 1],
  ASM: ["ASM (second moment angulaire)", 1],
  entropy: ["Entropie", 10],
};

function TextureTab({ d }: { d: Descriptors }) {
  const maxLbp = Math.max(...d.lbp.values, 1e-9);
  return (
    <div className="flex flex-wrap gap-7">
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-3">
        <SectionTitle title="Texture GLCM" hint="3 distances × 4 angles" />
        {Object.entries(d.glcm).map(([key, v]) => {
          const [label, max] = GLCM_LABELS[key] ?? [key, 1];
          return (
            <div key={key} className="flex flex-col gap-1.5">
              <div className="flex justify-between text-[13px]">
                <span>{label}</span>
                <span className="font-semibold tabular-nums">{num(v)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[#eef0f5]">
                <div className="h-full rounded-full bg-ink" style={{ width: `${Math.min(100, (Math.abs(v) / max) * 100)}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-3">
        <SectionTitle title="Histogramme LBP" hint={`P = ${d.lbp.P}, R = ${d.lbp.R}`} />
        <div className="grid h-[180px] items-end gap-1.5 border-b border-line" style={{ gridTemplateColumns: `repeat(${d.lbp.values.length}, minmax(0, 1fr))` }}>
          {d.lbp.values.map((v, i) => (
            <div
              key={i}
              className="w-full rounded-t-[4px] rounded-b-[1px]"
              style={{ height: Math.max(3, (v / maxLbp) * 160), background: i === d.lbp.values.length - 1 ? "#F59E0B" : "#4338CA" }}
              title={`Motif ${i} : ${pct(v)}`}
            />
          ))}
        </div>
        <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${d.lbp.values.length}, minmax(0, 1fr))` }}>
          {d.lbp.values.map((_, i) => (
            <span key={i} className="text-center text-[11px] text-muted">
              {i}
            </span>
          ))}
        </div>
        <p className="m-0 text-xs leading-normal text-muted">
          Motifs uniformes 0 à {d.lbp.P} ; la case {d.lbp.P + 1} (orange) regroupe les motifs non uniformes.
        </p>
      </div>
    </div>
  );
}

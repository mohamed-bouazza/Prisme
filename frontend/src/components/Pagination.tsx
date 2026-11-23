/** Pagination : 1 … 4 5 [6] 7 8 … 250 */
import { formatCount } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function Pagination({ page, pages, total, perPage, onChange }: { page: number; pages: number; total: number; perPage: number; onChange: (p: number) => void }) {
  const around = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2].filter((p) => p >= 1 && p <= pages));
  const list = [...around].sort((a, b) => a - b);
  const first = (page - 1) * perPage + 1;
  const last = Math.min(page * perPage, total);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
      <span className="text-sm text-muted">
        Images {formatCount(first)} à {formatCount(last)} sur {formatCount(total)}
      </span>
      {pages > 1 && (
        <nav aria-label="Pagination" className="flex flex-wrap gap-1.5">
          {list.map((p, i) => (
            <span key={p} className="flex gap-1.5">
              {i > 0 && p - list[i - 1] > 1 && <span className="flex h-10 min-w-6 items-center justify-center text-muted">…</span>}
              <button
                type="button"
                aria-current={p === page ? "page" : undefined}
                onClick={() => onChange(p)}
                className={cn(
                  "flex h-10 min-w-10 cursor-pointer items-center justify-center rounded-[10px] px-2 text-sm",
                  p === page ? "bg-primary font-semibold text-white" : "border border-line bg-white text-ink hover:border-line-strong",
                )}
              >
                {p}
              </button>
            </span>
          ))}
        </nav>
      )}
    </div>
  );
}

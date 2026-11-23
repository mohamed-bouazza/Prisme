/**
 * Client de l'API du backend galerie : une fonction par route, avec les types des réponses.
 *
 * - Les requêtes partent vers /api (même origine grâce au proxy de Vite) : le navigateur envoie
 *   automatiquement le cookie d'authentification (httpOnly, illisible par JavaScript).
 * - Pour les requêtes qui MODIFIENT (POST, PATCH, DELETE), le backend exige l'en-tête X-CSRF-TOKEN,
 *   copie du cookie lisible "csrf_access_token" : un site tiers ne peut pas le lire, donc pas le forger.
 */

export type User = { id: number; email: string; username: string; created_at: string };

export type Category = {
  id: number;
  name: string;
  parent_id: number | null;
  public: boolean;
  image_count: number;
  total_count: number;
};

export type ImageItem = {
  id: number;
  filename: string;
  width: number;
  height: number;
  size_bytes: number;
  format: string;
  source: "dataset" | "upload" | "transform";
  category_id: number | null;
  parent_id: number | null;
  transform: Operation[] | null;
  indexed: boolean;
  public: boolean;
  mine: boolean;
  created_at: string;
  urls: { file: string; thumb: string; download: string };
};

export type ImageDetail = ImageItem & {
  category_path: { id: number; name: string }[];
  has_descriptors: boolean;
};

export type Page<T> = { items: T[]; total: number; page: number; per_page: number; pages: number };

export type Operation =
  | { op: "crop"; x: number; y: number; width: number; height: number }
  | { op: "resize"; width?: number; height?: number }
  | { op: "rotate"; angle: number }
  | { op: "flip"; direction: "horizontal" | "vertical" }
  | { op: "grayscale" }
  | { op: "brightness"; factor: number }
  | { op: "contrast"; factor: number }
  | { op: "blur"; radius: number };

export type Descriptors = {
  color_histogram: { bins: [number, number, number]; values: number[] };
  color_moments: Record<"H" | "S" | "V", { mean: number; std: number; skewness: number }>;
  dominant_colors: { hex: string; rgb: [number, number, number]; proportion: number }[];
  glcm: Record<string, number>;
  lbp: { P: number; R: number; values: number[] };
};

export type SearchResult = { rank: number; distance: number; image: ImageItem };
export type SearchResponse = {
  query: { type: "image"; image_id: number; filename: string } | { type: "upload"; filename: string };
  k: number;
  results: SearchResult[];
  cbir_ms: number | null;
};

export type FeedbackResponse = {
  k: number;
  results: SearchResult[];
  desc_weights: Record<string, number>;
  counts: Record<string, number>;
  n_relevant: number;
  n_nonrelevant: number;
  cbir_ms: number | null;
};

export type UploadResponse = {
  images: ImageItem[];
  errors: { filename: string; error: string }[];
  warnings: string[];
};

/** Erreur renvoyée par l'API : on garde le message et le code HTTP. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_access_token="))
    ?.split("=")[1];
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body; // le navigateur ajoute lui-même Content-Type: multipart/form-data; boundary=...
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (method !== "GET") {
    const token = csrfToken();
    if (token) headers["X-CSRF-TOKEN"] = token;
  }
  const res = await fetch("/api" + path, { method, headers, body: payload, credentials: "same-origin" });
  if (!res.ok) {
    let message = `Erreur ${res.status}`;
    try {
      const body = await res.json();
      // {"error": "..."} en général ; {"errors": [{filename, error}]} quand tous les fichiers d'un upload sont refusés
      message = body.error ?? body.errors?.[0]?.error ?? message;
    } catch {
      /* réponse non JSON (ex. serveur arrêté) : on garde le message générique */
    }
    if (res.status === 502 || res.status === 504) message = "Le serveur ne répond pas. Le backend est-il lancé ?";
    throw new ApiError(message, res.status);
  }
  if (res.headers.get("Content-Type")?.includes("application/json")) return res.json() as Promise<T>;
  return res.blob() as unknown as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? "?" + s : "";
};

export const api = {
  // --- authentification
  me: () => request<{ user: User }>("GET", "/auth/me"),
  login: (email: string, password: string) => request<{ user: User }>("POST", "/auth/login", { email, password }),
  register: (email: string, username: string, password: string) =>
    request<{ user: User }>("POST", "/auth/register", { email, username, password }),
  logout: () => request<{ ok: boolean }>("POST", "/auth/logout"),

  // --- catégories
  categories: () => request<{ categories: Category[] }>("GET", "/categories"),
  createCategory: (name: string, parent_id: number | null) =>
    request<{ category: Category }>("POST", "/categories", { name, parent_id }),
  updateCategory: (id: number, data: { name?: string; parent_id?: number | null }) =>
    request<{ category: Category }>("PATCH", `/categories/${id}`, data),
  deleteCategory: (id: number) => request<{ deleted: number[] }>("DELETE", `/categories/${id}`),

  // --- images
  images: (params: {
    scope?: string;
    category_id?: number | null;
    uncategorized?: boolean;
    q?: string;
    order?: string;
    page?: number;
    per_page?: number;
  }) =>
    request<Page<ImageItem>>(
      "GET",
      "/images" + qs({ ...params, uncategorized: params.uncategorized ? 1 : undefined }),
    ),
  image: (id: number) => request<{ image: ImageDetail }>("GET", `/images/${id}`),
  upload: (files: File[], categoryId: number | null) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (categoryId !== null) fd.append("category_id", String(categoryId));
    return request<UploadResponse>("POST", "/images", fd);
  },
  updateImage: (id: number, data: { filename?: string; category_id?: number | null }) =>
    request<{ image: ImageItem }>("PATCH", `/images/${id}`, data),
  deleteImages: (ids: number[]) => request<{ deleted: number[]; warnings: string[] }>("POST", "/images/bulk-delete", { ids }),
  downloadZip: (ids: number[]) => request<Blob>("POST", "/images/download", { ids }),
  transform: (id: number, operations: Operation[], filename?: string, category_id?: number | null) =>
    request<{ image: ImageItem; warnings: string[] }>("POST", `/images/${id}/transform`, {
      operations,
      ...(filename ? { filename } : {}),
      ...(category_id !== undefined ? { category_id } : {}),
    }),
  descriptors: (id: number) =>
    request<{ image_id: number; cached: boolean; descriptors: Descriptors }>("GET", `/images/${id}/descriptors`),
  reindex: (id: number) => request<{ indexed: boolean; warnings: string[] }>("POST", `/images/${id}/reindex`),

  // --- recherche
  searchById: (image_id: number, k: number, desc_weights?: Record<string, number>) =>
    request<SearchResponse>("POST", "/search", { image_id, k, ...(desc_weights ? { desc_weights } : {}) }),
  searchByFile: (file: File, k: number, desc_weights?: Record<string, number>) => {
    const fd = new FormData();
    fd.append("image", file);
    fd.append("k", String(k));
    if (desc_weights) fd.append("desc_weights", JSON.stringify(desc_weights));
    return request<SearchResponse>("POST", "/search", fd);
  },
  /** Retour de pertinence FRE : on renvoie TOUS les marquages cumulés depuis le début de la session. */
  feedback: (query: { imageId: number } | { file: File }, relevant: number[], nonRelevant: number[], k: number) => {
    if ("imageId" in query)
      return request<FeedbackResponse>("POST", "/search/feedback", {
        image_id: query.imageId,
        relevant_ids: relevant,
        non_relevant_ids: nonRelevant,
        k,
      });
    const fd = new FormData();
    fd.append("image", query.file);
    fd.append("relevant_ids", JSON.stringify(relevant));
    fd.append("non_relevant_ids", JSON.stringify(nonRelevant));
    fd.append("k", String(k));
    return request<FeedbackResponse>("POST", "/search/feedback", fd);
  },
};

/** Déclenche l'enregistrement d'un Blob par le navigateur (téléchargement du ZIP). */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

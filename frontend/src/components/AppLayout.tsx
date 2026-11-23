/** Mise en page des pages connectées : barre latérale sombre (navigation + arbre des catégories) + contenu. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, FolderPlus, LayoutGrid, LogOut, Pencil, Plus, Search, Trash2, UserRound } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { CategoryDialog } from "@/components/CategoryDialog";
import { Logo } from "@/components/Logo";
import { Modal, Button, Spinner } from "@/components/ui";
import { api, type Category } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { buildTree, type CategoryNode, useCategories } from "@/lib/hooks";
import { cn, formatCount } from "@/lib/utils";

/** Redirige vers /connexion si personne n'est connecté. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  if (!user) return <Navigate to="/connexion" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-wrap bg-canvas">
      <Sidebar />
      <main className="flex min-w-0 flex-[999_1_560px] flex-col">
        <Outlet />
      </main>
    </div>
  );
}

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const location = useLocation();
  const scopeMine = location.pathname === "/" && params.get("scope") === "mine";

  const navClass = (active: boolean) =>
    cn(
      "flex h-[42px] items-center gap-3 rounded-[10px] px-3 text-sm no-underline",
      active ? "bg-ink-2 font-semibold text-white" : "font-medium text-side-text hover:bg-ink-2/60 hover:text-white",
    );

  return (
    <aside className="flex w-full flex-col gap-7 bg-ink px-4 py-6 text-side-text md:sticky md:top-0 md:h-screen md:w-[272px] md:flex-none md:overflow-y-auto">
      <Link to="/" className="flex items-center gap-2.5 px-2 no-underline">
        <Logo size={28} />
        <span className="font-display text-[19px] font-bold text-white">Prisme</span>
      </Link>

      <nav aria-label="Navigation principale" className="flex flex-col gap-0.5">
        <NavLink to="/" end className={({ isActive }) => navClass(isActive && !scopeMine)}>
          <LayoutGrid className="size-[18px]" aria-hidden />
          Galerie
        </NavLink>
        <NavLink to="/recherche" className={({ isActive }) => navClass(isActive)}>
          <Search className="size-[18px]" aria-hidden />
          Recherche
        </NavLink>
        <Link to="/?scope=mine" className={navClass(scopeMine)}>
          <UserRound className="size-[18px]" aria-hidden />
          Mes images
        </Link>
      </nav>

      <CategoryTree />

      <div className="mt-auto flex items-center gap-3 rounded-xl bg-ink-3 p-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-white">
          {user?.username.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-semibold text-white">{user?.username}</span>
          <span className="truncate text-xs text-side-muted">{user?.email}</span>
        </div>
        <button
          type="button"
          aria-label="Se déconnecter"
          title="Se déconnecter"
          onClick={async () => {
            await logout();
            navigate("/connexion");
          }}
          className="flex size-9 cursor-pointer items-center justify-center rounded-lg text-side-muted hover:bg-ink-2 hover:text-white"
        >
          <LogOut className="size-[18px]" />
        </button>
      </div>
    </aside>
  );
}

function CategoryTree() {
  const { data: categories, isPending } = useCategories();
  const [params] = useSearchParams();
  const location = useLocation();
  const active = location.pathname === "/" ? Number(params.get("cat")) || null : null;
  const [dialog, setDialog] = useState<{ open: boolean; editing?: Category | null; parent?: number | null }>({ open: false });
  const [toDelete, setToDelete] = useState<Category | null>(null);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const remove = useMutation({
    mutationFn: (c: Category) => api.deleteCategory(c.id),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["categories"] });
      qc.invalidateQueries({ queryKey: ["images"] });
      toast.success(`${r.deleted.length} catégorie(s) supprimée(s), les images sont conservées`);
      if (active && r.deleted.includes(active)) navigate("/");
      setToDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const tree = buildTree(categories ?? []);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="px-3 text-xs font-semibold uppercase tracking-[0.06em] text-side-muted">Catégories</span>
      {isPending && <Spinner className="mx-3 size-5 text-side-muted" />}
      <ul className="m-0 flex list-none flex-col gap-px p-0">
        {tree.map((n) => (
          <TreeItem
            key={n.id}
            node={n}
            active={active}
            onEdit={(c) => setDialog({ open: true, editing: c })}
            onAddChild={(c) => setDialog({ open: true, parent: c.id })}
            onDelete={setToDelete}
          />
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setDialog({ open: true })}
        className="mt-1 flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-dashed border-[#36415a] bg-transparent px-3 text-[13px] font-medium text-side-text hover:border-side-muted hover:text-white"
      >
        <Plus className="size-3.5" aria-hidden />
        Nouvelle catégorie
      </button>

      <CategoryDialog open={dialog.open} editing={dialog.editing} defaultParent={dialog.parent ?? null} onClose={() => setDialog({ open: false })} />
      <Modal
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Supprimer la catégorie ?"
        description={`« ${toDelete?.name} » et toutes ses sous-catégories seront supprimées. Les images ne sont pas supprimées : elles deviennent « sans catégorie ».`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setToDelete(null)}>
              Annuler
            </Button>
            <Button variant="danger" loading={remove.isPending} onClick={() => toDelete && remove.mutate(toDelete)} icon={<Trash2 className="size-4" />}>
              Supprimer
            </Button>
          </>
        }
      >
        {null}
      </Modal>
    </div>
  );
}

function TreeItem({
  node,
  active,
  onEdit,
  onAddChild,
  onDelete,
}: {
  node: CategoryNode;
  active: number | null;
  onEdit: (c: Category) => void;
  onAddChild: (c: Category) => void;
  onDelete: (c: Category) => void;
}) {
  // GHIM-10K est replié par défaut sauf si une de ses sous-catégories est ouverte
  const containsActive = (n: CategoryNode): boolean => n.id === active || n.children.some(containsActive);
  const [open, setOpen] = useState(() => !node.public || containsActive(node));
  const isActive = node.id === active;
  const hasChildren = node.children.length > 0;

  return (
    <li>
      <div
        className={cn(
          "group flex h-9 items-center gap-1 rounded-lg pr-2 text-sm",
          isActive ? "bg-[#26305f] font-semibold text-white" : "text-side-text hover:bg-ink-2/70",
        )}
        style={{ paddingLeft: 4 + node.depth * 16 }}
      >
        <button
          type="button"
          aria-label={open ? `Replier ${node.name}` : `Déplier ${node.name}`}
          onClick={() => setOpen(!open)}
          className={cn("flex size-6 shrink-0 cursor-pointer items-center justify-center rounded text-side-muted hover:text-white", !hasChildren && "invisible")}
        >
          {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <Link to={`/?cat=${node.id}`} className="min-w-0 flex-1 truncate text-inherit no-underline">
          {node.name}
        </Link>
        {!node.public && (
          <span className="hidden items-center gap-0.5 group-hover:flex group-focus-within:flex">
            <TreeAction label={`Ajouter une sous-catégorie à ${node.name}`} onClick={() => onAddChild(node)}>
              <FolderPlus className="size-3.5" />
            </TreeAction>
            <TreeAction label={`Modifier ${node.name}`} onClick={() => onEdit(node)}>
              <Pencil className="size-3.5" />
            </TreeAction>
            <TreeAction label={`Supprimer ${node.name}`} onClick={() => onDelete(node)}>
              <Trash2 className="size-3.5" />
            </TreeAction>
          </span>
        )}
        <span className="text-xs text-side-muted group-hover:hidden group-focus-within:hidden">{formatCount(node.total_count)}</span>
      </div>
      {open && hasChildren && (
        <ul className="m-0 flex list-none flex-col gap-px p-0">
          {node.children.map((c) => (
            <TreeItem key={c.id} node={c} active={active} onEdit={onEdit} onAddChild={onAddChild} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </li>
  );
}

function TreeAction({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex size-6 cursor-pointer items-center justify-center rounded text-side-muted hover:bg-ink hover:text-white"
    >
      {children}
    </button>
  );
}

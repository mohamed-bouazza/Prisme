/** Connexion / inscription. À gauche : présentation ; à droite : le formulaire. */
import { ArrowRight } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { Logo } from "@/components/Logo";
import { Button, Field, Input, Segmented } from "@/components/ui";
import { useAuth } from "@/lib/auth";

// Six petites miniatures de GHIM-10K copiées dans public/login/ : la page de connexion est visible
// AVANT d'être connecté, elle ne peut donc pas utiliser les routes protégées du backend.
const MOSAIC = ["sunset", "butterfly", "sea", "flowers", "temples", "mountains"];

export function LoginPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={(location.state as { from?: string } | null)?.from ?? "/"} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, username, password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-wrap bg-canvas">
      <section className="flex min-w-0 flex-[1_1_560px] flex-col gap-10 bg-ink px-8 py-12 text-[#e6e9f0] sm:px-16 sm:py-14">
        <div className="flex flex-wrap items-center gap-3">
          <Logo />
          <span className="font-display text-[22px] font-bold tracking-tight text-white">Prisme</span>
          <span className="rounded-full border border-[#2a3348] px-2.5 py-0.5 text-[13px] text-[#9aa3b5]">Galerie CBIR · Groupe 14</span>
        </div>
        <div className="flex max-w-[560px] flex-col gap-4">
          <h1 className="m-0 font-display text-4xl leading-[1.08] font-semibold tracking-[-0.02em] text-white sm:text-5xl">
            Retrouvez une image par ce qu'elle contient.
          </h1>
          <p className="m-0 text-[17px] leading-relaxed text-[#b7bfce]">
            Couleurs, textures, motifs : choisissez une image, marquez les résultats pertinents, et la recherche apprend ce que vous cherchez.
          </p>
        </div>
        <div className="grid max-w-[560px] grid-cols-3 gap-3" aria-hidden>
          {MOSAIC.map((m) => (
            <img key={m} src={`/login/${m}.jpg`} alt="" className="block aspect-[4/3] w-full rounded-xl object-cover" />
          ))}
        </div>
        <div className="mt-auto flex flex-wrap gap-10">
          {[
            ["10 000", "images GHIM-10K"],
            ["20", "catégories"],
            ["5", "descripteurs couleur et texture"],
          ].map(([n, l]) => (
            <div key={l} className="flex flex-col gap-1">
              <span className="font-display text-[28px] font-semibold text-white">{n}</span>
              <span className="text-[13px] text-[#9aa3b5]">{l}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="flex min-w-0 flex-[1_1_480px] items-center justify-center px-6 py-14">
        <form
          onSubmit={submit}
          className="flex w-full max-w-[420px] flex-col gap-6 rounded-[20px] border border-line bg-white p-8 shadow-[0_24px_48px_-24px_rgba(14,21,37,.18)] sm:p-10"
        >
          <div className="flex flex-col gap-1.5">
            <h2 className="m-0 font-display text-[28px] font-semibold tracking-tight">{mode === "login" ? "Connexion" : "Créer un compte"}</h2>
            <p className="m-0 text-[15px] text-muted">
              {mode === "login" ? "Accédez à votre galerie et à la recherche." : "Quelques secondes suffisent."}
            </p>
          </div>

          <Segmented
            label="Choisir"
            value={mode}
            onChange={(m) => {
              setMode(m);
              setError(null);
            }}
            options={[
              { value: "login", label: "Se connecter" },
              { value: "register", label: "Créer un compte" },
            ]}
          />

          <Field label="Adresse email" htmlFor="email">
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-12" />
          </Field>
          {mode === "register" && (
            <Field label="Nom d'utilisateur" htmlFor="username">
              <Input id="username" required minLength={2} maxLength={80} value={username} onChange={(e) => setUsername(e.target.value)} className="h-12" />
            </Field>
          )}
          <Field label="Mot de passe" htmlFor="password" hint={mode === "register" ? "8 caractères minimum" : undefined}>
            <Input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-12"
            />
          </Field>

          {error && (
            <p role="alert" className="m-0 rounded-xl bg-reject-soft px-4 py-3 text-sm font-medium text-reject-ink">
              {error}
            </p>
          )}

          <Button type="submit" size="lg" loading={busy} className="h-[52px]">
            {mode === "login" ? "Se connecter" : "Créer mon compte"}
            {!busy && <ArrowRight className="size-[18px]" aria-hidden />}
          </Button>
        </form>
      </section>
    </div>
  );
}

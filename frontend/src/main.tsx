/** Point d'entrée : fournisseurs globaux (données, session, notifications) + routes. */
import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { Toaster } from "sonner";

import { AppLayout, RequireAuth } from "@/components/AppLayout";
import { AuthProvider } from "@/lib/auth";
import { GalleryPage } from "@/pages/GalleryPage";
import { ImagePage } from "@/pages/ImagePage";
import { LoginPage } from "@/pages/LoginPage";
import { SearchPage } from "@/pages/SearchPage";
import { TransformPage } from "@/pages/TransformPage";

// TanStack Query met en cache les réponses de l'API : revenir sur une page déjà vue est instantané.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  { path: "/connexion", element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { path: "/", element: <GalleryPage /> },
      { path: "/images/:id", element: <ImagePage /> },
      { path: "/images/:id/transformer", element: <TransformPage /> },
      { path: "/recherche", element: <SearchPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Toaster position="bottom-right" richColors closeButton />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);

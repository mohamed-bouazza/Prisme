// Configuration de Vite (serveur de développement + compilation).
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // "@/..." = "src/..." : des imports courts et indépendants de la profondeur du fichier
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // Proxy : le navigateur appelle /api sur le MÊME port que la page (5173) et Vite transmet au
    // backend galerie (5000). Même origine => les cookies d'authentification fonctionnent sans CORS.
    proxy: { "/api": { target: "http://127.0.0.1:5000", changeOrigin: false } },
  },
});

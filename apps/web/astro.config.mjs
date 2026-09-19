import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://huntsman1756.github.io",
  base: "/finreg-es",
  trailingSlash: "always",
  integrations: [sitemap()],
  build: { format: "directory" },
});

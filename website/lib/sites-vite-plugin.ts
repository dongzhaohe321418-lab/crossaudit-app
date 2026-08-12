// This plugin lives in `lib/`, not `build/`, on purpose. The OpenAI Sites
// starter shipped it under `build/`, but the repository root `.gitignore`
// ignores every `build/` directory, so the file never reached the repo and a
// clean clone could not run `npm run build` or `npm test` (vite.config.ts
// imported a path that only existed on the original author's machine).
// Keeping it here — a path Git actually tracks — is what prevents that
// silent-until-clone failure. Only the vinext/Cloudflare path needs this
// plugin; `next build` (the Vercel path) never loads vite.config.ts.
import { access, cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return false;
    }
    throw error;
  }
}

// Packages Sites metadata and migrations after Vite finishes compiling.
export function sites(): Plugin {
  let root = process.cwd();

  return {
    name: "sites",
    apply: "build",
    configResolved(config) {
      root = config.root;
    },
    async closeBundle() {
      const outputDirectory = resolve(root, "dist", ".openai");
      const hostingConfig = resolve(root, ".openai", "hosting.json");
      const drizzleSource = resolve(root, "drizzle");

      await rm(outputDirectory, { recursive: true, force: true });
      await mkdir(outputDirectory, { recursive: true });

      if (await exists(hostingConfig)) {
        await cp(hostingConfig, resolve(outputDirectory, "hosting.json"));
      }
      if (await exists(drizzleSource)) {
        await cp(drizzleSource, resolve(outputDirectory, "drizzle"), {
          recursive: true,
        });
      }
    },
  };
}

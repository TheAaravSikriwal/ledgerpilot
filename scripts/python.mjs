// Resolves the backend virtualenv's Python on any OS.
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const root = join(dirname(fileURLToPath(import.meta.url)), "..");
export const backend = join(root, "backend");
export const venvPython = join(
  backend,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
export const hasVenv = () => existsSync(venvPython);

// One-time setup: Python virtualenv + backend deps, then frontend deps.
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { backend, hasVenv, root, venvPython } from "./python.mjs";

function run(cmd, args, cwd) {
  console.log(`\n> ${cmd} ${args.join(" ")}`);
  const result = spawnSync(cmd, args, { cwd, stdio: "inherit", shell: process.platform === "win32" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!hasVenv()) {
  const python = process.platform === "win32" ? "python" : "python3";
  run(python, ["-m", "venv", ".venv"], backend);
}
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"], backend);
run(venvPython, ["-m", "pip", "install", "-e", ".[dev]"], backend);
run("npm", ["install"], join(root, "frontend"));
console.log("\nSetup complete. Start the app with:  npm run dev");

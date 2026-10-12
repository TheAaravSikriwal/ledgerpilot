// Runs backend lint + tests with the virtualenv's Python.
import { spawnSync } from "node:child_process";
import { backend, venvPython } from "./python.mjs";

for (const args of [["-m", "ruff", "check", "ledgerpilot", "tests"], ["-m", "pytest"]]) {
  const r = spawnSync(venvPython, args, { cwd: backend, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

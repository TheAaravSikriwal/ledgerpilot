// Starts the FastAPI backend on 127.0.0.1:8000 with auto-reload.
import { spawn } from "node:child_process";
import { backend, hasVenv, venvPython } from "./python.mjs";

if (!hasVenv()) {
  console.error("Backend virtualenv missing. Run:  npm run setup");
  process.exit(1);
}
const args = [
  "-m", "uvicorn", "ledgerpilot.main:create_app", "--factory",
  "--host", "127.0.0.1", "--port", "8000", "--reload", "--reload-dir", "ledgerpilot",
];
const child = spawn(venvPython, args, { cwd: backend, stdio: "inherit" });
child.on("exit", (code) => process.exit(code ?? 0));
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));

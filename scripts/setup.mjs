import { spawnSync } from "node:child_process";
import { existsSync, copyFileSync, chmodSync } from "node:fs";
function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
if (Number(process.versions.node.split(".")[0]) < 22) {
  console.error("EventWeave needs Node 22.22 or newer.");
  process.exit(1);
}
if (!existsSync(".env")) {
  copyFileSync(".env.example", ".env");
  chmodSync(".env", 0o600);
  console.log(
    "Created a private .env file. Add your service configuration before starting the API.",
  );
}
run("npm", ["ci"]);
run("python3", ["-m", "venv", "--without-pip", ".venv"]);
run("python3", [
  "-m",
  "pip",
  "--python",
  ".venv",
  "install",
  "-r",
  existsSync("requirements.lock") ? "requirements.lock" : "requirements.txt",
]);
run(".venv/bin/python", ["scripts/contracts.py", "--check"]);
run("npm", ["run", "build"]);
console.log("Setup complete. Run npm run db:migrate, then npm run dev.");

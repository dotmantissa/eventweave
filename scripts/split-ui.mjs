import ts from "typescript";
import { readFileSync, writeFileSync } from "node:fs";
const path = "apps/web/src/App.tsx";
const input = readFileSync(path, "utf8");
const source = ts.createSourceFile(
  path,
  input,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);
const imports = [];
for (const st of source.statements) {
  if (ts.isImportDeclaration(st)) {
    const clause = st.importClause;
    const bindings = clause?.namedBindings;
    const names =
      bindings && ts.isNamedImports(bindings)
        ? bindings.elements.map((el) => ({
            name: el.name.text,
            type: el.isTypeOnly,
            original: el.getText(source),
          }))
        : [];
    imports.push({ module: st.moduleSpecifier.text, names });
  }
}
const functions = new Map(
  source.statements
    .filter(ts.isFunctionDeclaration)
    .map((n) => [n.name.text, n]),
);
const constants = source.statements.filter(ts.isVariableStatement);
const commonNames = [
  "Mark",
  "Status",
  "Notice",
  "Empty",
  "PageIntro",
  "Feedback",
  "kindLabels",
  "statusLabels",
  "formatDate",
];
function emit(filename, nodes, extra = [], isCommon = false) {
  let body = nodes.map((n) => n.getText(source)).join("\n\n");
  const used = new Set();
  for (const n of nodes) {
    function visit(x) {
      if (ts.isIdentifier(x)) used.add(x.text);
      ts.forEachChild(x, visit);
    }
    visit(n);
  }
  const lines = [];
  for (const imp of imports) {
    const names = imp.names.filter((n) => used.has(n.name));
    if (!names.length) continue;
    let module = imp.module;
    if (filename !== path && module.startsWith("./"))
      module = "../" + module.slice(2);
    lines.push(
      "import {" +
        names.map((n) => n.original).join(",") +
        "} from '" +
        module +
        "';",
    );
  }
  if (!isCommon) {
    const shared = commonNames.filter((n) => used.has(n));
    if (shared.length)
      lines.push("import {" + shared.join(",") + "} from '../components/ui';");
    if (used.has("useEvents"))
      lines.push("import {useEvents} from '../hooks/use-events';");
  }
  if (isCommon) body = body.replace(/^(function|const) /gm, "export $1 ");
  if (filename.includes("/pages/"))
    body = body.replace(/^function /, "export default function ");
  if (filename.includes("/hooks/"))
    body = body.replace(/^function /, "export function ");
  writeFileSync(
    filename,
    lines.concat(extra).join("\n") + "\n\n" + body + "\n",
  );
}
emit(
  "apps/web/src/components/ui.tsx",
  [...constants, ...commonNames.map((n) => functions.get(n)).filter(Boolean)],
  [],
  true,
);
emit("apps/web/src/hooks/use-events.ts", [functions.get("useEvents")]);
const pages = [
  "Registry",
  "EventDetail",
  "Workspace",
  "NewEvent",
  "Challenges",
  "Applications",
  "Activity",
  "Guide",
];
for (const name of pages)
  emit("apps/web/src/pages/" + name + ".tsx", [functions.get(name)]);
const app = functions.get("App");
emit(
  path,
  [app],
  pages.map((name) => "import " + name + " from './pages/" + name + "';"),
);
let root = readFileSync(path, "utf8").replace(
  "from '../components/ui'",
  "from './components/ui'",
);
writeFileSync(path, root);

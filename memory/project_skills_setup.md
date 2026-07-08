---
name: project-skills-setup
description: "Skille i pluginy Claude Code w repo — gdzie żyją, jak instalować/usuwać, pułapki (skills-lock, scope pluginów, symlink na Windows)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 26c8d5ee-dcec-430b-8896-77b338211a42
---

Skille projektowe (od 2026-07-08) są commitowane do repo, żeby działały na obu
komputerach użytkownika: `.agents/skills/` (źródło zarządzane przez `npx skills`) +
`.claude/skills/` (czyta Claude Code) + `skills-lock.json`. Zainstalowane:
`frontend-design` (anthropics/skills), `find-skills` (vercel-labs/skills).
Pluginy projektu w `.claude/settings.json` → `enabledPlugins`:
`document-skills@anthropic-agent-skills`, `claude-api@anthropic-agent-skills`.

**Why:** użytkownik pracuje na kilku komputerach ([[project-github]] — repo jest
źródłem prawdy dla ciągłości); instalacja per-projekt w repo zamiast globalnej
(`-g`) była świadomą decyzją po commicie skilli.

**How to apply:**
- Instalacja: `npx skills add <github-url> --skill <nazwa>`, potem przejrzeć
  SKILL.md (skille działają z pełnymi uprawnieniami), commit + push na etap2.
- Usuwanie skilla: `npx skills remove <nazwa> -y` usuwa pliki, ale NIE czyści
  wpisu w `skills-lock.json` — usunąć ręcznie, inaczej lock kłamie.
- Usuwanie pluginu projektowego: najpierw wpis z `enabledPlugins` w
  `.claude/settings.json`, potem `claude plugin uninstall <nazwa> --scope project`
  (domyślny scope `user` → komenda zawodzi z mylącym komunikatem).
- Symlink `.claude/skills/<nazwa>` → `.agents/skills/<nazwa>` git na Windows
  rozwija do zwykłych plików — zostawić tak (kopia przeżywa checkout na innym
  komputerze, absolutny symlink by nie przeżył).
- Skill nieprzydatny w tym repo (np. React-owy `vercel-react-best-practices`,
  usunięty 2026-07-08) → nie instalować per-projekt; do innych projektów `-g`.

---
description: Create a conventional git commit with emoji from staged or unstaged changes
argument-hint: "[message] [--push] [--no-verify]"
---
# Commit Command

You are an AI coding agent helping create a clean, well-formed git commit for this repository.

User arguments: `$ARGUMENTS`

## Workflow

1. **Interpret arguments**
   - If the user supplied a plain commit message in `$ARGUMENTS`, use it as the commit description after selecting the best emoji/type unless it already includes a full conventional prefix.
   - If `$ARGUMENTS` includes `--push`, push after a successful commit.
   - If `$ARGUMENTS` includes `--no-verify`, skip validation commands.

2. **Inspect repository state**
   - Run `git status --short`.
   - If nothing is changed, report that there is nothing to commit and stop.
   - If files are already staged, commit only staged files.
   - If no files are staged, run `git add .` to stage all current changes.

3. **Validate when appropriate**
   - Unless `--no-verify` is present, run project-appropriate validation if available:
     - If `package.json` exists: prefer `pnpm lint`/`pnpm build` when pnpm files exist; otherwise use npm/yarn equivalents when scripts exist.
     - If `pyproject.toml` exists: run available checks such as `ruff check .`, `pytest`, or project documented commands when configured.
     - If no clear validation command exists, skip validation and say why.
   - If validation fails, explain the failure and ask whether to fix issues or proceed. Do not commit failed validation without user confirmation.

4. **Analyze staged changes**
   - Run `git diff --cached --stat` and `git diff --cached`.
   - Identify the primary change type, scope, and intent.
   - Prefer one atomic commit. If staged changes are unrelated, tell the user and suggest splitting.

5. **Generate commit message**
   - Format: `<emoji> <type>: <imperative description>`.
   - Keep the first line under 72 characters.
   - Use present-tense imperative mood, e.g. `add`, `fix`, `update`, `remove`.
   - Choose the most appropriate emoji/type from the reference below.

6. **Commit**
   - Show the proposed message before committing.
   - Run `git commit -m "<message>"`.
   - After success, show the short commit hash and a brief summary.
   - If `--push` was supplied, run `git push` and report the result.

## Emoji/type reference

- ✨ `feat`: new feature
- 🐛 `fix`: bug fix
- 📝 `docs`: documentation
- 💄 `style`: formatting/style only
- ♻️ `refactor`: refactoring without behavior change
- ⚡️ `perf`: performance improvement
- ✅ `test`: tests
- 🔧 `chore`: tooling/config/maintenance
- 🚀 `ci`: CI/CD
- 🗑️ `revert`: revert changes
- 🚨 `fix`: compiler/linter warnings
- 🔒️ `fix`: security fix
- 🚚 `refactor`: move or rename files/resources
- 🏗️ `refactor`: architecture changes
- 📦️ `chore`: package/build artifacts
- ➕ `chore`: add dependency
- ➖ `chore`: remove dependency
- 🧑‍💻 `chore`: developer experience
- 🏷️ `feat`: types/schema updates
- 👔 `feat`: business logic
- 🩹 `fix`: minor/simple fix
- 🥅 `fix`: error handling
- 🔥 `fix`: remove code/files
- ✏️ `fix`: typos
- 🙈 `chore`: .gitignore changes
- 🗃️ `db`: database changes
- 🔊 `feat`: add/update logs
- 🔇 `fix`: remove logs
- 🦺 `feat`: validation logic

## Examples

- ✨ feat: add user authentication flow
- 🐛 fix: resolve file upload timeout
- 📝 docs: update deployment instructions
- ♻️ refactor: simplify data indexing pipeline
- ✅ test: add coverage for project controller
- 🔧 chore: update Docker environment templates

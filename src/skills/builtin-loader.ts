import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import type { Skill } from "../types.js";
import { parseSkillMd } from "./format.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BUILTIN_SKILLS_DIR = path.resolve(__dirname, "../../skills/revenue");

export function loadBuiltinSkills(db: { upsertSkill: (skill: Skill) => void }): void {
  if (!fs.existsSync(BUILTIN_SKILLS_DIR)) return;

  const entries = fs.readdirSync(BUILTIN_SKILLS_DIR, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const skillMdPath = path.join(BUILTIN_SKILLS_DIR, entry.name, "SKILL.md");
    if (!fs.existsSync(skillMdPath)) continue;

    const content = fs.readFileSync(skillMdPath, "utf-8");
    const skill = parseSkillMd(content, skillMdPath, "builtin");
    if (skill) {
      db.upsertSkill(skill);
    }
  }
}

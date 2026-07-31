import type { Profile, Proficiency } from './profile.js'

export interface RoleRequirement {
  skillId: string
  minimumProficiency: Proficiency
  required: boolean
}

export interface MatchExplanation {
  skillId: string
  status: 'met' | 'below-level' | 'missing'
  required: boolean
  verified: boolean
}

export interface MatchResult {
  /** 0–100, rounded. */
  score: number
  /** False when any required skill is missing or below the requested level. */
  eligible: boolean
  explanations: MatchExplanation[]
}

const PROFICIENCY_RANK: Record<Proficiency, number> = {
  beginner: 1,
  intermediate: 2,
  advanced: 3,
  expert: 4,
}

const REQUIRED_WEIGHT = 3
const OPTIONAL_WEIGHT = 1
/** A verified skill counts slightly more than a self-declared one. */
const VERIFIED_BONUS = 0.25

/**
 * Deterministic, fully explainable skill matching. Ranking that decides who
 * gets seen must be auditable, so the model-assisted features in the roadmap
 * layer on top of this score rather than replacing it.
 */
export function matchProfileToRole(profile: Profile, requirements: RoleRequirement[]): MatchResult {
  if (requirements.length === 0) {
    return { score: 0, eligible: true, explanations: [] }
  }

  const bySkillId = new Map(profile.skills.map((skill) => [skill.id, skill]))
  let earned = 0
  let available = 0
  let eligible = true

  const explanations = requirements.map((requirement): MatchExplanation => {
    const weight = requirement.required ? REQUIRED_WEIGHT : OPTIONAL_WEIGHT
    const skill = bySkillId.get(requirement.skillId)
    const verified = (skill?.verifications.length ?? 0) > 0
    available += weight * (1 + VERIFIED_BONUS)

    if (!skill) {
      if (requirement.required) eligible = false
      return { skillId: requirement.skillId, status: 'missing', required: requirement.required, verified: false }
    }

    const meetsLevel =
      PROFICIENCY_RANK[skill.proficiency] >= PROFICIENCY_RANK[requirement.minimumProficiency]

    if (!meetsLevel) {
      if (requirement.required) eligible = false
      // Partial credit: the skill is present, just not yet at the level asked for.
      earned += weight * 0.5 * (verified ? 1 + VERIFIED_BONUS : 1)
      return { skillId: requirement.skillId, status: 'below-level', required: requirement.required, verified }
    }

    earned += weight * (verified ? 1 + VERIFIED_BONUS : 1)
    return { skillId: requirement.skillId, status: 'met', required: requirement.required, verified }
  })

  return {
    score: Math.round((earned / available) * 100),
    eligible,
    explanations,
  }
}

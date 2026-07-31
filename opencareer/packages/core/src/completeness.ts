import type { Profile } from './profile.js'

export interface CompletenessCheck {
  key: string
  label: string
  weight: number
  satisfied: boolean
}

export interface CompletenessReport {
  /** 0–100, rounded. */
  score: number
  checks: CompletenessCheck[]
  /** Unsatisfied checks, heaviest first — what to show the person next. */
  suggestions: CompletenessCheck[]
}

const CHECKS: Array<{ key: string; label: string; weight: number; test: (p: Profile) => boolean }> = [
  { key: 'headline', label: 'Write a headline', weight: 10, test: (p) => p.headline.trim().length >= 10 },
  { key: 'bio', label: 'Describe yourself', weight: 10, test: (p) => (p.bio?.trim().length ?? 0) >= 120 },
  { key: 'video-intro', label: 'Record a video introduction', weight: 25, test: (p) => p.videoIntro !== undefined },
  { key: 'skills', label: 'List at least five skills', weight: 15, test: (p) => p.skills.length >= 5 },
  {
    key: 'verified-skills',
    label: 'Get at least one skill verified',
    weight: 10,
    test: (p) => p.skills.some((skill) => skill.verifications.length > 0),
  },
  { key: 'experience', label: 'Add your work history', weight: 15, test: (p) => p.experiences.length >= 1 },
  {
    key: 'verified-experience',
    label: 'Get one position verified by the employer',
    weight: 5,
    test: (p) => p.experiences.some((exp) => exp.verified),
  },
  { key: 'portfolio', label: 'Publish portfolio work', weight: 10, test: (p) => p.portfolio.length >= 1 },
]

/**
 * Scores how usable a profile is for discovery. Weights favour the formats a
 * static resume cannot carry — video and verified history — because those are
 * what the platform exists to surface.
 */
export function scoreCompleteness(profile: Profile): CompletenessReport {
  const checks = CHECKS.map(({ key, label, weight, test }) => ({
    key,
    label,
    weight,
    satisfied: test(profile),
  }))

  const total = checks.reduce((sum, check) => sum + check.weight, 0)
  const earned = checks.reduce((sum, check) => (check.satisfied ? sum + check.weight : sum), 0)

  return {
    score: Math.round((earned / total) * 100),
    checks,
    suggestions: checks.filter((check) => !check.satisfied).sort((a, b) => b.weight - a.weight),
  }
}

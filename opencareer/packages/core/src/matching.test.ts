import { describe, expect, it } from 'vitest'
import { matchProfileToRole, type RoleRequirement } from './matching.js'
import { buildProfile } from './testing.js'

const requirements: RoleRequirement[] = [
  { skillId: 'go', minimumProficiency: 'advanced', required: true },
  { skillId: 'postgres', minimumProficiency: 'intermediate', required: false },
]

describe('matchProfileToRole', () => {
  it('marks a candidate ineligible when a required skill is missing', () => {
    const result = matchProfileToRole(buildProfile(), requirements)

    expect(result.eligible).toBe(false)
    expect(result.score).toBe(0)
    expect(result.explanations).toEqual([
      { skillId: 'go', status: 'missing', required: true, verified: false },
      { skillId: 'postgres', status: 'missing', required: false, verified: false },
    ])
  })

  it('gives partial credit below the requested level but keeps the candidate ineligible', () => {
    const result = matchProfileToRole(
      buildProfile({
        skills: [{ id: 'go', name: 'Go', proficiency: 'beginner' }],
      }),
      requirements,
    )

    expect(result.eligible).toBe(false)
    expect(result.score).toBeGreaterThan(0)
    expect(result.explanations[0]?.status).toBe('below-level')
  })

  it('scores a verified, fully qualified candidate at 100', () => {
    const result = matchProfileToRole(
      buildProfile({
        skills: [
          { id: 'go', name: 'Go', proficiency: 'expert', verifications: ['assessment:go-2025'] },
          { id: 'postgres', name: 'PostgreSQL', proficiency: 'advanced', verifications: ['peer:acme'] },
        ],
      }),
      requirements,
    )

    expect(result).toMatchObject({ score: 100, eligible: true })
    expect(result.explanations.every((e) => e.status === 'met' && e.verified)).toBe(true)
  })

  it('ranks a verified skill above an identical unverified one', () => {
    const unverified = matchProfileToRole(
      buildProfile({ skills: [{ id: 'go', name: 'Go', proficiency: 'expert' }] }),
      [requirements[0]!],
    )
    const verified = matchProfileToRole(
      buildProfile({
        skills: [{ id: 'go', name: 'Go', proficiency: 'expert', verifications: ['assessment:go-2025'] }],
      }),
      [requirements[0]!],
    )

    expect(verified.score).toBeGreaterThan(unverified.score)
    expect(unverified.eligible).toBe(true)
  })

  it('treats a role with no requirements as an open call', () => {
    expect(matchProfileToRole(buildProfile(), [])).toEqual({ score: 0, eligible: true, explanations: [] })
  })
})

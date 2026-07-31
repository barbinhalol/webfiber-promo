import { describe, expect, it } from 'vitest'
import { OPP_VERSION, profileSchema } from './profile.js'
import { buildProfile } from './testing.js'

describe('profileSchema', () => {
  it('stamps the OPP version and applies array defaults', () => {
    const profile = buildProfile()

    expect(profile.oppVersion).toBe(OPP_VERSION)
    expect(profile.skills).toEqual([])
    expect(profile.experiences).toEqual([])
    expect(profile.openToWork).toBe(false)
  })

  it('rejects handles that are not URL safe', () => {
    expect(() => buildProfile({ handle: 'Ana Souza' })).toThrow(/lowercase alphanumeric/)
  })

  it('rejects an experience that ends before it starts', () => {
    expect(() =>
      buildProfile({
        experiences: [
          {
            id: 'exp_1',
            organization: 'Acme',
            title: 'Engineer',
            startDate: '2024-06',
            endDate: '2023-01',
          },
        ],
      }),
    ).toThrow(/endDate must not be earlier/)
  })

  it('accepts an open-ended current position', () => {
    const profile = buildProfile({
      experiences: [
        { id: 'exp_1', organization: 'Acme', title: 'Engineer', startDate: '2024-06' },
      ],
    })

    expect(profile.experiences[0]?.endDate).toBeUndefined()
    expect(profile.experiences[0]?.verified).toBe(false)
  })

  it('round-trips a parsed profile without loss', () => {
    const profile = buildProfile({
      videoIntro: { kind: 'video', url: 'https://cdn.example.com/ana.mp4', title: 'Hello' },
    })

    expect(profileSchema.parse(JSON.parse(JSON.stringify(profile)))).toEqual(profile)
  })
})

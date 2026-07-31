import { describe, expect, it } from 'vitest'
import { scoreCompleteness } from './completeness.js'
import { buildProfile } from './testing.js'

describe('scoreCompleteness', () => {
  it('scores a bare profile on the headline alone', () => {
    const report = scoreCompleteness(buildProfile())

    expect(report.score).toBe(10)
    expect(report.suggestions[0]?.key).toBe('video-intro')
  })

  it('rewards the video introduction most heavily', () => {
    const withVideo = scoreCompleteness(
      buildProfile({
        videoIntro: { kind: 'video', url: 'https://cdn.example.com/ana.mp4', title: 'Hello' },
      }),
    )

    expect(withVideo.score).toBe(35)
    expect(withVideo.suggestions.some((s) => s.key === 'video-intro')).toBe(false)
  })

  it('reaches 100 for a fully populated profile', () => {
    const report = scoreCompleteness(
      buildProfile({
        bio: 'Backend engineer with a decade of experience building payment and identity systems for companies across Latin America, mostly in Go and TypeScript.',
        videoIntro: { kind: 'video', url: 'https://cdn.example.com/ana.mp4', title: 'Hello' },
        portfolio: [{ kind: 'link', url: 'https://github.com/ana', title: 'GitHub' }],
        skills: ['go', 'typescript', 'postgres', 'kubernetes', 'grpc'].map((id, index) => ({
          id,
          name: id,
          proficiency: 'advanced',
          verifications: index === 0 ? ['assessment:go-2025'] : [],
        })),
        experiences: [
          {
            id: 'exp_1',
            organization: 'Acme',
            title: 'Staff Engineer',
            startDate: '2021-02',
            verified: true,
          },
        ],
      }),
    )

    expect(report.score).toBe(100)
    expect(report.suggestions).toEqual([])
  })
})

import { parseProfile, type Profile } from './profile.js'

/** Builds a valid profile for tests and local seeding. */
export function buildProfile(overrides: Record<string, unknown> = {}): Profile {
  return parseProfile({
    id: 'prf_1',
    handle: 'ana-souza',
    fullName: 'Ana Souza',
    headline: 'Backend engineer focused on distributed systems',
    updatedAt: '2026-01-15T10:00:00.000Z',
    ...overrides,
  })
}

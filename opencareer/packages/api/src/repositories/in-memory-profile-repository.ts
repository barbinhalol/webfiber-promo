import { parseProfile, type Profile, type ProfileInput } from '@opencareer/core'
import { HandleTakenError, type ProfileRepository } from './profile-repository.js'

export interface Clock {
  now(): Date
}

/**
 * Development and test adapter. The Postgres adapter behind the same interface
 * is tracked in ROADMAP.md; keeping persistence behind a port is what lets a
 * self-hosted instance swap storage without touching the routes.
 */
export class InMemoryProfileRepository implements ProfileRepository {
  readonly #profiles = new Map<string, Profile>()
  readonly #clock: Clock
  #sequence = 0

  constructor(clock: Clock = { now: () => new Date() }) {
    this.#clock = clock
  }

  async create(input: ProfileInput): Promise<Profile> {
    const handle = input.handle
    if (this.#profiles.has(handle)) {
      throw new HandleTakenError(handle)
    }

    const profile = this.#materialize(`prf_${++this.#sequence}`, input)
    this.#profiles.set(handle, profile)
    return profile
  }

  async findByHandle(handle: string): Promise<Profile | undefined> {
    return this.#profiles.get(handle)
  }

  async list(options: { openToWork?: boolean } = {}): Promise<Profile[]> {
    const profiles = [...this.#profiles.values()]
    const filtered =
      options.openToWork === undefined
        ? profiles
        : profiles.filter((profile) => profile.openToWork === options.openToWork)

    return filtered.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  }

  async replace(handle: string, input: ProfileInput): Promise<Profile | undefined> {
    const existing = this.#profiles.get(handle)
    if (!existing) return undefined

    if (input.handle !== handle && this.#profiles.has(input.handle)) {
      throw new HandleTakenError(input.handle)
    }

    const updated = this.#materialize(existing.id, input)
    this.#profiles.delete(handle)
    this.#profiles.set(updated.handle, updated)
    return updated
  }

  async delete(handle: string): Promise<boolean> {
    return this.#profiles.delete(handle)
  }

  #materialize(id: string, input: ProfileInput): Profile {
    return parseProfile({ ...input, id, updatedAt: this.#clock.now().toISOString() })
  }
}

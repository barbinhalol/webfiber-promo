import type { Profile, ProfileInput } from '@opencareer/core'

export interface ProfileRepository {
  create(input: ProfileInput): Promise<Profile>
  findByHandle(handle: string): Promise<Profile | undefined>
  list(options?: { openToWork?: boolean }): Promise<Profile[]>
  replace(handle: string, input: ProfileInput): Promise<Profile | undefined>
  delete(handle: string): Promise<boolean>
}

export class HandleTakenError extends Error {
  constructor(handle: string) {
    super(`handle "${handle}" is already in use`)
    this.name = 'HandleTakenError'
  }
}

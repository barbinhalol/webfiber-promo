export {
  OPP_VERSION,
  experienceSchema,
  mediaSchema,
  parseProfile,
  profileInputSchema,
  profileSchema,
  proficiencySchema,
  skillSchema,
} from './profile.js'
export type { Experience, Media, Profile, ProfileInput, Proficiency, Skill } from './profile.js'

export { scoreCompleteness } from './completeness.js'
export type { CompletenessCheck, CompletenessReport } from './completeness.js'

export { matchProfileToRole } from './matching.js'
export type { MatchExplanation, MatchResult, RoleRequirement } from './matching.js'

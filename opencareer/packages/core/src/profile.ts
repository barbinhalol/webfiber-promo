import { z } from 'zod'

/**
 * Open Professional Profile (OPP) — the portable document at the centre of
 * OpenCareer. A profile is owned by the person it describes: it can be
 * exported, re-imported into another instance, or served from a self-hosted
 * deployment without losing meaning. See docs/data-model.md.
 */

export const OPP_VERSION = '0.1.0'

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}(-\d{2})?$/, 'expected an ISO date as YYYY-MM or YYYY-MM-DD')

export const proficiencySchema = z.enum(['beginner', 'intermediate', 'advanced', 'expert'])

export const skillSchema = z.object({
  /** Stable identifier inside a taxonomy, e.g. `esco:1234` or `opencareer:typescript`. */
  id: z.string().min(1),
  name: z.string().min(1).max(80),
  proficiency: proficiencySchema,
  yearsOfExperience: z.number().min(0).max(60).optional(),
  /** Endorsement or assessment records that back this claim. */
  verifications: z.array(z.string().min(1)).default([]),
})

export const experienceSchema = z
  .object({
    id: z.string().min(1),
    organization: z.string().min(1).max(120),
    title: z.string().min(1).max(120),
    startDate: isoDate,
    /** Absent means "current position". */
    endDate: isoDate.optional(),
    summary: z.string().max(2_000).optional(),
    skillIds: z.array(z.string().min(1)).default([]),
    /** Set once an employer or an accredited partner confirms the record. */
    verified: z.boolean().default(false),
  })
  .refine((exp) => !exp.endDate || exp.endDate >= exp.startDate, {
    message: 'endDate must not be earlier than startDate',
    path: ['endDate'],
  })

export const mediaSchema = z.object({
  kind: z.enum(['video', 'image', 'document', 'link']),
  url: z.string().url(),
  title: z.string().min(1).max(160),
  description: z.string().max(1_000).optional(),
})

export const profileSchema = z.object({
  oppVersion: z.literal(OPP_VERSION).default(OPP_VERSION),
  id: z.string().min(1),
  handle: z
    .string()
    .min(3)
    .max(39)
    .regex(/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/, 'handle must be lowercase alphanumeric with dashes'),
  fullName: z.string().min(1).max(120),
  headline: z.string().min(1).max(160),
  /** Short written pitch. The video introduction is the primary format. */
  bio: z.string().max(4_000).optional(),
  location: z.string().max(120).optional(),
  languages: z.array(z.string().min(2).max(35)).default([]),
  /** 60–120s self-recorded introduction — the resume replacement. */
  videoIntro: mediaSchema.extend({ kind: z.literal('video') }).optional(),
  portfolio: z.array(mediaSchema).default([]),
  skills: z.array(skillSchema).default([]),
  experiences: z.array(experienceSchema).default([]),
  openToWork: z.boolean().default(false),
  updatedAt: z.string().datetime(),
})

export type Proficiency = z.infer<typeof proficiencySchema>
export type Skill = z.infer<typeof skillSchema>
export type Experience = z.infer<typeof experienceSchema>
export type Media = z.infer<typeof mediaSchema>
export type Profile = z.infer<typeof profileSchema>

/** Fields a profile owner may submit; server-owned fields are excluded. */
export const profileInputSchema = profileSchema.omit({
  id: true,
  updatedAt: true,
  oppVersion: true,
})

export type ProfileInput = z.input<typeof profileInputSchema>

export function parseProfile(value: unknown): Profile {
  return profileSchema.parse(value)
}

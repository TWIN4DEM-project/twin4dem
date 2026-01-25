import {z} from "zod";


export const UserSettingsListItemSchema = z.object({
  id: z.number(),
  label: z.string(),
  governmentSize: z.number(),
  governmentConnectivityDegree: z.number(),
  parliamentSize: z.number(),
  courtSize: z.number(),
});
export const UserSettingsListSchema = z.array(UserSettingsListItemSchema);
export type UserSettingsListItem = z.infer<typeof UserSettingsListItemSchema>;
export type UserSettingsList = UserSettingsListItem[];

export const PartySettingsSchema = z.object({
    id: z.number(),
    label: z.string(),
    memberCount: z.number(),
    position: z.literal(["majority", "opposition", "independent"])
})
export const UserSettingsSchema = z.object({
    id: z.number(),
    userId: z.number(),
    label: z.string(),
    governmentSize: z.number(),
    governmentConnectivityDegree: z.number(),
    governmentProbabilityFor: z.number(),
    parliamentMajorityProbabilityFor: z.number(),
    parliamentOppositionProbabilityFor: z.number(),
    courtProbabilityFor: z.number(),
    parliamentSize: z.number(),
    courtSize: z.number(),
    officeRetentionSensitivity: z.number(),
    socialInfluenceSusceptibility: z.number(),
    abstentionThreshold: z.number(),
    dataUpdateFrequency: z.number(),
    legislativePathProbability: z.number(),
    parties: z.array(PartySettingsSchema)
})
export type UserSettings = z.infer<typeof UserSettingsSchema>;
export type PartySettings = z.infer<typeof PartySettingsSchema>;
export type PartySettingsList = PartySettings[];
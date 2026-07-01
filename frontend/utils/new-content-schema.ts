import { z } from 'zod';

export const newContentFormSchema = z.object({
  campaignAngle: z.string().min(1, 'زاویه کمپین الزامی است'),
  tone: z.string().min(1),
  language: z.enum(['فارسی', 'انگلیسی']),
  draftCount: z.number().min(1).max(5),
});

export type NewContentFormValues = z.infer<typeof newContentFormSchema>;

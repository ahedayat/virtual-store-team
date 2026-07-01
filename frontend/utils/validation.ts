import { z } from 'zod';

export const phoneSchema = z
  .string()
  .min(1, 'شماره موبایل الزامی است')
  .refine((val) => val.startsWith('09'), {
    message: 'شماره موبایل باید با 09 شروع شود',
  });

export const otpSchema = z
  .string()
  .length(6, 'کد تایید باید دقیقاً ۶ رقم باشد')
  .regex(/^\d{6}$/, 'کد تایید باید فقط شامل اعداد باشد');

export type PhoneFormValues = z.infer<typeof phoneSchema>;
export type OtpFormValues = z.infer<typeof otpSchema>;

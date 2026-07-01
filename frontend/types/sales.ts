export type RecType =
  | 'همه'
  | 'شارژ'
  | 'تخفیف کالا'
  | 'تخفیف زماندار'
  | 'کوپن عمومی'
  | 'کوپن فردی'
  | 'پیگیری';

export type Recommendation = {
  id: number;
  type: Exclude<RecType, 'همه'>;
  priority: number;
  title: string;
  description: string;
  reason: string;
  payload: Record<string, string>;
};

export type EditForm = {
  title: string;
  description: string;
  reason: string;
};

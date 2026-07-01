export type ContentType = 'همه' | 'کپشن اینستاگرام' | 'توضیحات محصول';

export type ContentItem = {
  id: number;
  type: Exclude<ContentType, 'همه'>;
  product: string;
  content: string;
  reason: string;
  status: string;
};

export type NewContentType = 'کپشن اینستاگرام' | 'توضیحات محصول';

export type ContentStep = 1 | 2 | 3;

export type Product = {
  id: number;
  name: string;
};

export type GeneratedDraft = {
  id: number;
  content: string;
  reason: string;
};

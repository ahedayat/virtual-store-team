'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  ChevronRight,
  Sparkles,
  Check,
  Image as ImageIcon,
  AlignRight,
  Settings,
  Layers,
} from 'lucide-react';
import { useProducts } from '@/hooks/use-products';
import { useNewContentStore } from '@/stores/new-content-store';
import type { NewContentType } from '@/types/content';
import {
  newContentFormSchema,
  type NewContentFormValues,
} from '@/utils/new-content-schema';
import styles from './NewContentPage.module.css';

const steps = [
  { num: 1, label: 'انتخاب نوع', icon: Layers },
  { num: 2, label: 'تنظیمات', icon: Settings },
  { num: 3, label: 'بررسی', icon: Sparkles },
] as const;

export function NewContentPage() {
  const router = useRouter();
  const { data: products, isLoading } = useProducts();

  const step = useNewContentStore((s) => s.step);
  const type = useNewContentStore((s) => s.type);
  const selectedProducts = useNewContentStore((s) => s.selectedProducts);
  const isGenerating = useNewContentStore((s) => s.isGenerating);
  const generatedDrafts = useNewContentStore((s) => s.generatedDrafts);
  const selectedDraftId = useNewContentStore((s) => s.selectedDraftId);
  const setStep = useNewContentStore((s) => s.setStep);
  const setType = useNewContentStore((s) => s.setType);
  const toggleProduct = useNewContentStore((s) => s.toggleProduct);
  const setIsGenerating = useNewContentStore((s) => s.setIsGenerating);
  const setGeneratedDrafts = useNewContentStore((s) => s.setGeneratedDrafts);
  const setSelectedDraftId = useNewContentStore((s) => s.setSelectedDraftId);

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<NewContentFormValues>({
    resolver: zodResolver(newContentFormSchema),
    defaultValues: {
      campaignAngle: '',
      tone: 'لوکس و رسمی',
      language: 'فارسی',
      draftCount: 2,
    },
  });

  const campaignAngle = watch('campaignAngle');
  const progressWidth = step === 1 ? '0%' : step === 2 ? '50%' : '100%';

  const handleTypeSelect = (contentType: NewContentType) => {
    setType(contentType);
    setStep(2);
  };

  const handleGenerate = handleSubmit(() => {
    if (selectedProducts.length === 0) return;

    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setStep(3);
      setGeneratedDrafts([
        {
          id: 1,
          content:
            type === 'کپشن اینستاگرام'
              ? '✨ زیبایی در سادگیست.\n\nکالکشن جدید کیف‌های چرم ما با طراحی مینیمال و کیفیت بی‌نظیر، همراه همیشگی شما در لحظات خاص خواهد بود.\n\n🛍️ سفارش از طریق لینک بیو'
              : 'این محصول با استفاده از بهترین نوع چرم طبیعی و یراق‌آلات وارداتی تولید شده است. طراحی ارگونومیک و فضای داخلی بهینه‌سازی شده، آن را به انتخابی هوشمندانه تبدیل کرده است.',
          reason: 'لحن لوکس و رسمی رعایت شده و تمرکز بر کیفیت متریال است.',
        },
        {
          id: 2,
          content:
            type === 'کپشن اینستاگرام'
              ? 'استایلت رو با یه انتخاب خاص کامل کن! 💫\n\nکیف‌های جدیدمون رسیدن و منتظرن تا بشن بخش جدانشدنی از استایل روزمره‌ت. سبک، جادار و فوق‌العاده شیک.\n\n👇 همین الان از سایت سفارش بده'
              : 'طراحی مدرن در کنار اصالت چرم طبیعی. این کیف با ابعاد استاندارد و وزن سبک، مناسب استفاده روزمره و محیط‌های کاری است. دارای دو محفظه اصلی و یک جیب زیپ‌دار داخلی.',
          reason: 'لحن کمی صمیمی‌تر برای ایجاد ارتباط بهتر با مخاطب جوان.',
        },
      ]);
    }, 2000);
  });

  const handleCreate = () => {
    router.push('/content-agent');
  };

  const canGenerate =
    selectedProducts.length > 0 && campaignAngle && !isGenerating;

  return (
    <div className={`${styles.page} fadeIn`}>
      <div className={styles.backHeader}>
        <Link href="/content-agent" className={styles.backLink}>
          <ChevronRight style={{ width: '1.5rem', height: '1.5rem' }} />
        </Link>
        <div>
          <h1 className={styles.title}>ساخت محتوای جدید</h1>
          <p className={styles.subtitle}>تنظیمات تولید محتوا توسط هوش مصنوعی</p>
        </div>
      </div>

      <div className={styles.progress}>
        <div className={styles.progressLine} />
        <div className={styles.progressFill} style={{ width: progressWidth }} />
        {steps.map((s) => {
          const Icon = s.icon;
          const isActive = step >= s.num;
          return (
            <div key={s.num} className={styles.step}>
              <div
                className={`${styles.stepCircle} ${isActive ? styles.stepCircleActive : styles.stepCircleInactive}`}
              >
                <Icon style={{ width: '1.25rem', height: '1.25rem' }} />
              </div>
              <span
                className={`${styles.stepLabel} ${isActive ? styles.stepLabelActive : styles.stepLabelInactive}`}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {step === 1 && (
        <div className={`${styles.typeGrid} slideInRight`}>
          <button type="button" onClick={() => handleTypeSelect('کپشن اینستاگرام')} className={`${styles.typeCard} glass`}>
            <div className={`${styles.typeIconWrap} ${styles.typeIconInsta}`}>
              <ImageIcon className={styles.typeIcon} />
            </div>
            <div>
              <h3 className={styles.typeTitle}>کپشن اینستاگرام</h3>
              <p className={styles.typeDesc}>
                تولید کپشن‌های جذاب و تعاملی برای پست‌ها و ریلزهای اینستاگرام با
                هشتگ‌های مرتبط.
              </p>
            </div>
          </button>
          <button type="button" onClick={() => handleTypeSelect('توضیحات محصول')} className={`${styles.typeCard} glass`}>
            <div className={`${styles.typeIconWrap} ${styles.typeIconProduct}`}>
              <AlignRight className={styles.typeIcon} />
            </div>
            <div>
              <h3 className={styles.typeTitle}>توضیحات محصول</h3>
              <p className={styles.typeDesc}>
                تولید توضیحات دقیق، سئو شده و ترغیب‌کننده برای صفحات محصول در
                وب‌سایت.
              </p>
            </div>
          </button>
        </div>
      )}

      {step === 2 && (
        <form onSubmit={handleGenerate} className={`${styles.formCard} glass slideInRight`}>
          <div className={styles.formHeader}>
            <h2 className={styles.formTitle}>
              {type === 'کپشن اینستاگرام' ? (
                <ImageIcon style={{ width: '1.25rem', height: '1.25rem', color: '#db2777' }} />
              ) : (
                <AlignRight style={{ width: '1.25rem', height: '1.25rem', color: 'var(--agent-content)' }} />
              )}
              تنظیمات {type}
            </h2>
            <button type="button" onClick={() => setStep(1)} className={styles.changeTypeBtn}>
              تغییر نوع
            </button>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>محصول یا محصولات مرتبط</label>
            {isLoading ? (
              <div className={styles.loading}>در حال بارگذاری محصولات...</div>
            ) : (
              <div className={styles.productList}>
                {products?.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => toggleProduct(p.id)}
                    className={`${styles.productBtn} ${selectedProducts.includes(p.id) ? styles.productBtnActive : ''}`}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className={styles.field}>
            <label className={styles.label}>زاویه کمپین یا هدف محتوا</label>
            <input
              type="text"
              placeholder="مثلا: معرفی کالکشن جدید پاییزه، تمرکز روی هدیه روز مادر..."
              className={styles.input}
              {...register('campaignAngle')}
            />
            {errors.campaignAngle && (
              <span className={styles.errorText}>{errors.campaignAngle.message}</span>
            )}
          </div>

          <div className={styles.formGrid}>
            <div className={styles.field}>
              <label className={styles.label}>لحن برند</label>
              <select className={styles.select} {...register('tone')}>
                <option>لوکس و رسمی</option>
                <option>صمیمی و مینیمال</option>
                <option>هیجان‌انگیز و فروش‌محور</option>
              </select>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>زبان خروجی</label>
              <Controller
                name="language"
                control={control}
                render={({ field }) => (
                  <div className={styles.langToggle}>
                    {(['فارسی', 'انگلیسی'] as const).map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => field.onChange(lang)}
                        className={`${styles.langBtn} ${field.value === lang ? styles.langBtnActive : ''}`}
                      >
                        {lang}
                      </button>
                    ))}
                  </div>
                )}
              />
            </div>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>تعداد پیش‌نویس (Draft)</label>
            <div className={styles.rangeRow}>
              <Controller
                name="draftCount"
                control={control}
                render={({ field }) => (
                  <>
                    <input
                      type="range"
                      min={1}
                      max={5}
                      value={field.value}
                      onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
                      className={styles.range}
                    />
                    <span className={`${styles.rangeValue} tnum`}>{field.value}</span>
                  </>
                )}
              />
            </div>
          </div>

          <div className={styles.formFooter}>
            <button
              type="submit"
              disabled={!canGenerate}
              className={`${styles.generateBtn} ${canGenerate ? styles.generateBtnActive : styles.generateBtnDisabled}`}
            >
              {isGenerating ? (
                <>
                  <span className={styles.spinner} />
                  در حال پردازش...
                </>
              ) : (
                <>
                  <Sparkles style={{ width: '1.25rem', height: '1.25rem' }} />
                  تولید محتوای هوشمند
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {step === 3 && (
        <div className="slideInBottom">
          <div className={styles.resultsHeader}>
            <h2 className={styles.resultsTitle}>پیش‌نویس‌های تولید شده</h2>
            <button type="button" onClick={() => setStep(2)} className={styles.changeSettingsBtn}>
              تغییر تنظیمات
            </button>
          </div>

          <div className={styles.draftsGrid}>
            {generatedDrafts.map((draft) => (
              <div
                key={draft.id}
                onClick={() => setSelectedDraftId(draft.id)}
                className={`${styles.draftCard} glass ${selectedDraftId === draft.id ? styles.draftCardSelected : styles.draftCardDefault}`}
              >
                {selectedDraftId === draft.id && (
                  <div className={styles.checkMark}>
                    <Check style={{ width: '1rem', height: '1rem' }} />
                  </div>
                )}
                <div className={styles.draftContent}>{draft.content}</div>
                <div className={styles.reasonBox}>
                  <div className={styles.reasonTitle}>دلیل این پیشنهاد</div>
                  <div className={styles.reasonText}>{draft.reason}</div>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.stickyBar}>
            <button
              type="button"
              onClick={handleCreate}
              disabled={!selectedDraftId}
              className={`${styles.createBtn} ${selectedDraftId ? styles.createBtnActive : styles.createBtnDisabled}`}
            >
              ایجاد و ذخیره
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

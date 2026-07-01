'use client';

import {
  TrendingUp,
  Package,
  Tag,
  Clock,
  Users,
  UserPlus,
  MessageCircle,
  Edit3,
  Save,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { useRecommendations } from '@/hooks/use-recommendations';
import { useSalesStore } from '@/stores/sales-store';
import type { RecType } from '@/types/sales';
import styles from './SalesAgentPage.module.css';

const filters: RecType[] = [
  'همه',
  'شارژ',
  'تخفیف کالا',
  'تخفیف زماندار',
  'کوپن عمومی',
  'کوپن فردی',
  'پیگیری',
];

type TypeConfig = {
  icon: LucideIcon;
  badgeClass: string;
};

const getTypeConfig = (type: string): TypeConfig => {
  switch (type) {
    case 'شارژ':
      return { icon: Package, badgeClass: styles.badgeCharge };
    case 'تخفیف کالا':
      return { icon: Tag, badgeClass: styles.badgeDiscount };
    case 'تخفیف زماندار':
      return { icon: Clock, badgeClass: styles.badgeTimed };
    case 'کوپن عمومی':
      return { icon: Users, badgeClass: styles.badgePublic };
    case 'کوپن فردی':
      return { icon: UserPlus, badgeClass: styles.badgePersonal };
    case 'پیگیری':
      return { icon: MessageCircle, badgeClass: styles.badgeFollow };
    default:
      return { icon: TrendingUp, badgeClass: styles.badgeDefault };
  }
};

const stats = [
  { label: 'پیشنهاد فوری', val: '۲', colorClass: styles.statRose },
  { label: 'فرصت تخفیف', val: '۴', colorClass: styles.statOrange },
  { label: 'نیاز به شارژ', val: '۱', colorClass: styles.statBlue },
  { label: 'قابل پیگیری', val: '۵', colorClass: styles.statIndigo },
];

export function SalesAgentPage() {
  const { isLoading, isError } = useRecommendations();
  const filter = useSalesStore((s) => s.filter);
  const items = useSalesStore((s) => s.items);
  const editingId = useSalesStore((s) => s.editingId);
  const editForm = useSalesStore((s) => s.editForm);
  const setFilter = useSalesStore((s) => s.setFilter);
  const startEdit = useSalesStore((s) => s.startEdit);
  const updateEditField = useSalesStore((s) => s.updateEditField);
  const saveEdit = useSalesStore((s) => s.saveEdit);
  const removeItem = useSalesStore((s) => s.removeItem);

  const filteredItems = items.filter(
    (item) => filter === 'همه' || item.type === filter,
  );

  if (isLoading) {
    return <div className={styles.loading}>در حال بارگذاری...</div>;
  }

  if (isError) {
    return <div className={styles.error}>خطا در بارگذاری پیشنهادها</div>;
  }

  return (
    <div className={`${styles.page} fadeIn`}>
      <div className={`${styles.header} glass`}>
        <div className={styles.headerGlow} />
        <div className={styles.headerLeft}>
          <div className={styles.iconWrap}>
            <TrendingUp className={styles.headerIcon} />
          </div>
          <div>
            <h1 className={styles.title}>
              عامل فروش
              <span className={styles.liveDot}>
                <span className={styles.ping} />
                <span className={styles.dot} />
              </span>
            </h1>
            <p className={styles.subtitle}>
              پیشنهادهای هوشمند برای افزایش فروش، کاهش ضرر و پیگیری مشتریان
            </p>
          </div>
        </div>

        <div className={styles.statsGrid}>
          {stats.map((s) => (
            <div key={s.label} className={styles.statCard}>
              <div className={`${styles.statVal} tnum ${s.colorClass}`}>
                {s.val}
              </div>
              <div className={styles.statLabel}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className={`${styles.filters} scrollbarHide`}>
        {filters.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`${styles.filterBtn} ${filter === f ? styles.filterBtnActive : ''}`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className={styles.list}>
        {filteredItems.map((item) => {
          const isEditing = editingId === item.id;
          const config = getTypeConfig(item.type);
          const Icon = config.icon;

          return (
            <div key={item.id} className={`${styles.card} glass`}>
              <div className={styles.cardMain}>
                <div className={styles.cardTop}>
                  <div className={`${styles.typeBadge} ${config.badgeClass}`}>
                    <Icon className={styles.typeIcon} />
                    {item.type}
                  </div>
                  <div className={styles.priority}>
                    {[...Array(5)].map((_, i) => (
                      <div
                        key={i}
                        className={`${styles.priorityBar} ${i < item.priority ? styles.priorityActive : ''}`}
                      />
                    ))}
                  </div>
                </div>

                {isEditing ? (
                  <div className={styles.editForm}>
                    <input
                      value={editForm.title}
                      onChange={(e) =>
                        updateEditField('title', e.target.value)
                      }
                      className={styles.editTitle}
                    />
                    <textarea
                      value={editForm.description}
                      onChange={(e) =>
                        updateEditField('description', e.target.value)
                      }
                      className={styles.editTextarea}
                    />
                    <div>
                      <label className={styles.editLabel}>دلیل پیشنهاد</label>
                      <textarea
                        value={editForm.reason}
                        onChange={(e) =>
                          updateEditField('reason', e.target.value)
                        }
                        className={styles.editTextarea}
                      />
                    </div>
                  </div>
                ) : (
                  <>
                    <h2 className={styles.itemTitle}>{item.title}</h2>
                    <p className={styles.itemDesc}>{item.description}</p>
                    <div className={styles.reasonBox}>
                      <div className={styles.reasonHeader}>
                        <Sparkles className={styles.reasonIcon} />
                        دلیل پیشنهاد
                      </div>
                      <p className={styles.reasonText}>{item.reason}</p>
                    </div>
                  </>
                )}
              </div>

              <div className={styles.cardSide}>
                <div className={styles.payload}>
                  <div className={styles.payloadTitle}>جزئیات اقدام</div>
                  <div className={styles.payloadList}>
                    {Object.entries(item.payload).map(([key, value], i) => (
                      <div key={i} className={styles.payloadItem}>
                        <span className={styles.payloadKey}>{key}</span>
                        <span className={styles.payloadVal}>{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.actions}>
                  {isEditing ? (
                    <button
                      type="button"
                      onClick={() => saveEdit(item.id)}
                      className={styles.saveBtn}
                    >
                      <Save className={styles.actionIcon} /> ذخیره تغییرات
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => startEdit(item)}
                      className={styles.editBtn}
                    >
                      <Edit3 className={styles.actionIcon} /> ویرایش پیشنهاد
                    </button>
                  )}

                  <div className={styles.actionRow}>
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className={styles.cancelBtn}
                    >
                      انصراف
                    </button>
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className={styles.approveBtn}
                    >
                      تایید اقدام
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filteredItems.length === 0 && (
        <div className={styles.empty}>پیشنهادی در این دسته یافت نشد.</div>
      )}
    </div>
  );
}

'use client';

import Link from 'next/link';
import {
  PenTool,
  Plus,
  Check,
  X,
  Edit3,
  Save,
  Image as ImageIcon,
  AlignRight,
} from 'lucide-react';
import { useContentItems } from '@/hooks/use-content-items';
import { useContentStore } from '@/stores/content-store';
import type { ContentType } from '@/types/content';
import styles from './ContentAgentPage.module.css';

const filters: ContentType[] = ['همه', 'کپشن اینستاگرام', 'توضیحات محصول'];

export function ContentAgentPage() {
  const { isLoading, isError } = useContentItems();
  const filter = useContentStore((s) => s.filter);
  const items = useContentStore((s) => s.items);
  const editingId = useContentStore((s) => s.editingId);
  const editValue = useContentStore((s) => s.editValue);
  const setFilter = useContentStore((s) => s.setFilter);
  const startEdit = useContentStore((s) => s.startEdit);
  const setEditValue = useContentStore((s) => s.setEditValue);
  const saveEdit = useContentStore((s) => s.saveEdit);
  const removeItem = useContentStore((s) => s.removeItem);

  const filteredItems = items.filter(
    (item) => filter === 'همه' || item.type === filter,
  );

  if (isLoading) {
    return <div className={styles.loading}>در حال بارگذاری...</div>;
  }

  if (isError) {
    return <div className={styles.error}>خطا در بارگذاری محتوا</div>;
  }

  return (
    <div className={`${styles.page} fadeIn`}>
      <div className={`${styles.header} glass`}>
        <div className={styles.headerGlow} />
        <div className={styles.headerLeft}>
          <div className={styles.iconWrap}>
            <PenTool className={styles.headerIcon} />
          </div>
          <div>
            <h1 className={styles.title}>
              عامل محتوا
              <span className={styles.liveDot}>
                <span className={styles.ping} />
                <span className={styles.dot} />
              </span>
            </h1>
            <p className={styles.subtitle}>
              تولید هوشمند کپشن اینستاگرام و توضیحات محصول
            </p>
          </div>
        </div>
        <Link href="/content-agent/new-content" className={styles.newBtn}>
          <Plus style={{ width: '1.25rem', height: '1.25rem' }} />
          محتوای جدید
        </Link>
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

      <div className={styles.grid}>
        {filteredItems.map((item) => {
          const isInsta = item.type === 'کپشن اینستاگرام';
          const isEditing = editingId === item.id;
          const hasChanged = isEditing && editValue !== item.content;

          return (
            <div key={item.id} className={`${styles.card} glass`}>
              <div
                className={`${styles.cardHeader} ${isInsta ? styles.cardHeaderInsta : styles.cardHeaderDefault}`}
              >
                <div className={styles.typeRow}>
                  {isInsta ? (
                    <ImageIcon className={`${styles.typeIcon} ${styles.typeIconInsta}`} />
                  ) : (
                    <AlignRight className={`${styles.typeIcon} ${styles.typeIconDefault}`} />
                  )}
                  <span className={`${styles.typeLabel} ${isInsta ? styles.typeLabelInsta : styles.typeLabelDefault}`}>
                    {item.type}
                  </span>
                </div>
                <div className={styles.statusBadge}>{item.status}</div>
              </div>

              <div className={styles.cardBody}>
                <div>
                  <div className={styles.fieldLabel}>محصول</div>
                  <div className={styles.productName}>{item.product}</div>
                </div>

                <div className={styles.contentSection}>
                  <div className={styles.contentHeader}>
                    <span>متن پیشنهادی</span>
                    {!isEditing && (
                      <button type="button" onClick={() => startEdit(item)} className={styles.editBtn}>
                        <Edit3 style={{ width: '0.75rem', height: '0.75rem' }} /> ویرایش
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <textarea
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className={styles.textarea}
                      autoFocus
                    />
                  ) : (
                    <div onClick={() => startEdit(item)} className={styles.contentBox}>
                      {item.content}
                    </div>
                  )}
                </div>

                <div className={styles.reasonBox}>
                  <div className={styles.reasonTitle}>دلیل پیشنهاد</div>
                  <div className={styles.reasonText}>{item.reason}</div>
                </div>
              </div>

              <div className={styles.cardActions}>
                <button type="button" onClick={() => removeItem(item.id)} className={styles.rejectBtn}>
                  <X style={{ width: '1rem', height: '1rem' }} /> رد کردن
                </button>
                <div className={styles.actionRight}>
                  {isEditing ? (
                    <button
                      type="button"
                      onClick={() => saveEdit(item.id)}
                      disabled={!hasChanged}
                      className={`${styles.saveBtn} ${hasChanged ? styles.saveBtnActive : styles.saveBtnDisabled}`}
                    >
                      <Save style={{ width: '1rem', height: '1rem' }} /> ذخیره تغییرات
                    </button>
                  ) : (
                    <button type="button" onClick={() => removeItem(item.id)} className={styles.approveBtn}>
                      <Check style={{ width: '1rem', height: '1rem' }} /> تایید
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filteredItems.length === 0 && (
        <div className={styles.empty}>محتوایی در این دسته یافت نشد.</div>
      )}
    </div>
  );
}

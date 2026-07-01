'use client';

import {
  Network,
  PenTool,
  TrendingUp,
  MessageSquare,
  RefreshCw,
  FileText,
  CheckCircle2,
  AlertCircle,
  BarChart3,
  Clock,
  type LucideIcon,
} from 'lucide-react';
import { useCoordinatorStore } from '@/stores/coordinator-store';
import styles from './CoordinatorAgentPage.module.css';

type AgentCard = {
  name: string;
  icon: LucideIcon;
  iconClass: string;
  iconWrapClass: string;
  status: string;
  statusClass: string;
  items: string;
};

const agents: AgentCard[] = [
  {
    name: 'عامل محتوا',
    icon: PenTool,
    iconClass: styles.iconContent,
    iconWrapClass: styles.iconWrapContent,
    status: 'در انتظار بررسی',
    statusClass: styles.statusOrange,
    items: '۴ مورد',
  },
  {
    name: 'عامل فروش',
    icon: TrendingUp,
    iconClass: styles.iconSales,
    iconWrapClass: styles.iconWrapSales,
    status: 'فعال',
    statusClass: styles.statusGreen,
    items: '۸ پیشنهاد',
  },
  {
    name: 'عامل پشتیبانی',
    icon: MessageSquare,
    iconClass: styles.iconSupport,
    iconWrapClass: styles.iconWrapSupport,
    status: 'بدون مورد فوری',
    statusClass: styles.statusBlue,
    items: 'پاسخگو',
  },
];

const suggestedActions = [
  { text: 'تایید ۲ کپشن اینستاگرام برای انتشار عصر', agent: 'محتوا' },
  { text: 'بررسی پیشنهاد شارژ موجودی کیف لونا', agent: 'فروش' },
  { text: 'ارسال کد تخفیف برای ۳ سبد خرید رها شده', agent: 'فروش' },
];

export function CoordinatorAgentPage() {
  const isGenerating = useCoordinatorStore((s) => s.isGenerating);
  const lastUpdate = useCoordinatorStore((s) => s.lastUpdate);
  const setIsGenerating = useCoordinatorStore((s) => s.setIsGenerating);
  const setLastUpdate = useCoordinatorStore((s) => s.setLastUpdate);

  const handleGenerateReport = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setLastUpdate(
        `امروز، ${new Date().toLocaleTimeString('fa-IR', {
          hour: '2-digit',
          minute: '2-digit',
        })}`,
      );
    }, 3000);
  };

  return (
    <div className={`${styles.page} fadeIn`}>
      <div className={`${styles.header} glass`}>
        <div className={styles.headerGlow} />
        <div className={styles.headerLeft}>
          <div className={styles.iconWrap}>
            <Network className={styles.headerIcon} />
          </div>
          <div>
            <h1 className={styles.title}>
              عامل هماهنگ‌کننده
              <span className={styles.liveDot}>
                <span className={styles.ping} />
                <span className={styles.dot} />
              </span>
            </h1>
            <p className={styles.subtitle}>
              نمای کلی وضعیت فروشگاه و هماهنگی بین عامل‌ها
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className={`${styles.reportBtn} ${isGenerating ? styles.reportBtnDisabled : ''}`}
        >
          <RefreshCw
            className={`${styles.reportBtnIcon} ${isGenerating ? styles.spinning : ''}`}
          />
          {isGenerating ? 'در حال تحلیل داده‌ها...' : 'دریافت گزارش جدید'}
        </button>
      </div>

      <div className={styles.agentGrid}>
        {agents.map((agent) => {
          const Icon = agent.icon;
          return (
            <div key={agent.name} className={`${styles.agentCard} glass`}>
              <div className={styles.agentCardLeft}>
                <div className={`${styles.agentIconWrap} ${agent.iconWrapClass}`}>
                  <Icon className={`${styles.agentIcon} ${agent.iconClass}`} />
                </div>
                <div>
                  <div className={styles.agentName}>{agent.name}</div>
                  <div className={`${styles.agentStatus} ${agent.statusClass}`}>
                    {agent.status}
                  </div>
                </div>
              </div>
              <div className={styles.agentItems}>{agent.items}</div>
            </div>
          );
        })}
      </div>

      <div className={`${styles.reportCard} glass`}>
        {isGenerating && (
          <div className={styles.loadingOverlay}>
            <div className={styles.loadingSpinner}>
              <div className={styles.spinnerTrack} />
              <div className={styles.spinnerArc} />
              <Network className={styles.spinnerIcon} />
            </div>
            <div className={styles.loadingTitle}>
              در حال تحلیل داده‌های فروشگاه...
            </div>
            <div className={styles.loadingSubtitle}>
              ارتباط با عامل‌ها و استخراج گزارش
            </div>
          </div>
        )}

        <div className={styles.reportHeader}>
          <div className={styles.reportHeaderLeft}>
            <div className={styles.reportIconWrap}>
              <FileText className={styles.reportIcon} />
            </div>
            <div>
              <h2 className={styles.reportTitle}>گزارش روزانه فروشگاه</h2>
              <div className={styles.reportUpdate}>
                <Clock className={styles.updateIcon} /> آخرین بروزرسانی:{' '}
                {lastUpdate}
              </div>
            </div>
          </div>
          <div className={styles.overallStatus}>
            <CheckCircle2 className={styles.overallIcon} />
            وضعیت کلی: مطلوب
          </div>
        </div>

        <div className={styles.reportBody}>
          <div className={styles.leftCol}>
            <section>
              <h3 className={styles.sectionTitle}>
                <BarChart3 className={styles.sectionIcon} /> خلاصه فروش
              </h3>
              <div className={styles.salesGrid}>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>فروش امروز</div>
                  <div className={`${styles.statValue} tnum`}>
                    ۱۲,۵۰۰,۰۰۰{' '}
                    <span className={styles.statUnit}>تومان</span>
                  </div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>سفارشات موفق</div>
                  <div className={`${styles.statValue} tnum`}>
                    ۱۸ <span className={styles.statUnit}>عدد</span>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <h3 className={styles.sectionTitle}>
                <AlertCircle className={styles.sectionIcon} /> اقدامات پیشنهادی
                امروز
              </h3>
              <div className={styles.actionsList}>
                {suggestedActions.map((action, i) => (
                  <div key={i} className={styles.actionItem}>
                    <div className={styles.actionDot} />
                    <div className={styles.actionText}>{action.text}</div>
                    <div className={styles.actionAgent}>{action.agent}</div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className={styles.rightCol}>
            <h3 className={styles.deptTitle}>وضعیت دپارتمان‌ها</h3>

            <div className={styles.deptCard}>
              <div className={`${styles.deptIcon} ${styles.deptIconContent}`}>
                <PenTool className={styles.deptIconSvg} />
              </div>
              <div>
                <div className={styles.deptName}>وضعیت محتوا</div>
                <p className={styles.deptDesc}>
                  ۲ کپشن و ۲ توضیحات محصول آماده بررسی است. تقویم محتوایی این
                  هفته کامل شده است.
                </p>
              </div>
            </div>

            <div className={styles.deptCard}>
              <div className={`${styles.deptIcon} ${styles.deptIconSales}`}>
                <TrendingUp className={styles.deptIconSvg} />
              </div>
              <div>
                <div className={styles.deptName}>وضعیت پیشنهادهای فروش</div>
                <p className={styles.deptDesc}>
                  ۸ پیشنهاد فعال وجود دارد. اجرای پیشنهاد تخفیف زماندار می‌تواند
                  فروش آخر هفته را ۲۰٪ افزایش دهد.
                </p>
              </div>
            </div>

            <div className={styles.deptCard}>
              <div className={`${styles.deptIcon} ${styles.deptIconSupport}`}>
                <MessageSquare className={styles.deptIconSvg} />
              </div>
              <div>
                <div className={styles.deptName}>وضعیت پشتیبانی</div>
                <p className={styles.deptDesc}>
                  میانگین زمان پاسخگویی به زیر ۱۰ دقیقه کاهش یافته است. ۵ پیام
                  در انتظار تایید نهایی شماست.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import {
  Network,
  PenTool,
  TrendingUp,
  MessageSquare,
  CheckCircle2,
  Clock,
  AlertCircle,
  ChevronLeft,
} from 'lucide-react';
import { useDashboardStore } from '@/stores/dashboard-store';
import { priorityQueueItems } from '@/types/mock-data';
import { AgentNode } from './AgentNode';
import { StatCard } from './StatCard';
import styles from './DashboardPage.module.css';

const badgeClassMap = {
  content: styles.badgeContent,
  sales: styles.badgeSales,
  support: styles.badgeSupport,
};

export function DashboardPage() {
  const activeAgent = useDashboardStore((s) => s.activeAgent);
  const cycleActiveAgent = useDashboardStore((s) => s.cycleActiveAgent);

  useEffect(() => {
    const interval = setInterval(cycleActiveAgent, 3000);
    return () => clearInterval(interval);
  }, [cycleActiveAgent]);

  return (
    <div className={`${styles.page} fadeIn`}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>داشبورد مدیریت</h1>
          <p className={styles.subtitle}>
            نمای کلی وضعیت فروشگاه و فعالیت عامل‌های هوشمند
          </p>
        </div>
        <div className={`${styles.statusBadge} glass`}>
          <span className={styles.statusDot} />
          سیستم در وضعیت مطلوب
        </div>
      </div>

      <div className={`${styles.constellation} glass`}>
        <svg className={styles.svg}>
          <defs>
            <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(211,154,44,0.1)" />
              <stop offset="50%" stopColor="rgba(211,154,44,0.6)" />
              <stop offset="100%" stopColor="rgba(211,154,44,0.1)" />
            </linearGradient>
          </defs>
          <g
            stroke="url(#lineGrad)"
            strokeWidth="2"
            fill="none"
            strokeDasharray="6 6"
            className="dashFlow"
          >
            <path d="M 50% 50% L 50% 20%" />
            <path d="M 50% 50% L 75% 75%" />
            <path d="M 50% 50% L 25% 75%" />
          </g>
        </svg>

        <AgentNode
          icon={Network}
          label="عامل هماهنگ‌کننده"
          color="coordinator"
          isActive={activeAgent === 0}
          position="center"
        />
        <AgentNode
          icon={PenTool}
          label="عامل محتوا"
          color="content"
          isActive={activeAgent === 1}
          position="top"
        />
        <AgentNode
          icon={TrendingUp}
          label="عامل فروش"
          color="sales"
          isActive={activeAgent === 2}
          position="bottomRight"
        />
        <AgentNode
          icon={MessageSquare}
          label="عامل پشتیبانی"
          color="support"
          isActive={activeAgent === 3}
          position="bottomLeft"
        />
      </div>

      <div className={styles.statsGrid}>
        <StatCard title="کارهای در انتظار" value="۱۲" trend="۴+" trendUp={false} icon={Clock} colorClass="coordinator" />
        <StatCard title="پیام‌های پشتیبانی" value="۵" trend="۲-" trendUp icon={MessageSquare} colorClass="support" />
        <StatCard title="پیشنهادهای فروش" value="۸" trend="۳+" trendUp icon={TrendingUp} colorClass="sales" />
        <StatCard title="محتوای آماده" value="۴" trend="۱+" trendUp icon={PenTool} colorClass="content" />
        <StatCard title="فروش امروز" value="۱۲.۵M" trend="۱۵٪+" trendUp icon={CheckCircle2} colorClass="gold" />
        <StatCard title="وضعیت کلی" value="عالی" trend="پایدار" trendUp icon={AlertCircle} colorClass="sales" />
      </div>

      <div className={styles.bottomGrid}>
        <div className={`${styles.card} glass`}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>اقدامات نیازمند بررسی</h2>
            <Link href="/coordinator-agent" className={styles.viewAll}>
              مشاهده همه <ChevronLeft className={styles.chevron} />
            </Link>
          </div>
          <div className={styles.queueList}>
            {priorityQueueItems.map((item, i) => (
              <Link key={i} href={item.path} className={styles.queueItem}>
                <div className={styles.queueLeft}>
                  <div className={`${styles.agentBadge} ${badgeClassMap[item.colorClass as keyof typeof badgeClassMap]}`}>
                    {item.agent}
                  </div>
                  <div>
                    <div className={styles.queueTitle}>{item.title}</div>
                    <div className={styles.queueTime}>{item.time}</div>
                  </div>
                </div>
                <ChevronLeft className={styles.chevron} />
              </Link>
            ))}
          </div>
        </div>

        <div className={`${styles.card} ${styles.summaryCard} glass`}>
          <div className={styles.summaryGlow} />
          <div className={styles.summaryHeader}>
            <div className={styles.summaryIconWrap}>
              <Network className={styles.summaryIcon} />
            </div>
            <div>
              <h2 className={styles.summaryHeading}>خلاصه وضعیت امروز</h2>
              <p className={styles.summarySub}>گزارش عامل هماهنگ‌کننده</p>
            </div>
          </div>
          <div className={styles.summaryBody}>
            <p className={styles.summaryText}>
              روز خوبی را سپری می‌کنیم. فروش امروز ۱۵٪ نسبت به میانگین هفته گذشته
              افزایش داشته است. عامل فروش ۳ پیشنهاد جدید برای جلوگیری از اتمام
              موجودی کالاهای پرفروش آماده کرده است.
            </p>
            <div className={styles.recommendBox}>
              <div className={styles.recommendTitle}>
                <AlertCircle className={styles.summaryIcon} style={{ width: '1rem', height: '1rem', color: 'var(--agent-coordinator)' }} />
                توصیه اصلی امروز
              </div>
              <p className={styles.recommendText}>
                لطفا کپشن‌های آماده شده برای کمپین آخر هفته را بررسی کنید تا در
                زمان مناسب منتشر شوند. همچنین ۲ پیام پشتیبانی نیازمند تایید
                نهایی شماست.
              </p>
            </div>
            <Link href="/coordinator-agent" className={styles.reportBtn}>
              دریافت گزارش کامل
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

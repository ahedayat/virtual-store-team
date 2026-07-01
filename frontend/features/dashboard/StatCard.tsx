import type { LucideIcon } from 'lucide-react';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import styles from './StatCard.module.css';

type StatCardProps = {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
  icon: LucideIcon;
  colorClass: 'coordinator' | 'support' | 'sales' | 'content' | 'gold';
};

const iconColorMap = {
  coordinator: styles.iconCoordinator,
  support: styles.iconSupport,
  sales: styles.iconSales,
  content: styles.iconContent,
  gold: styles.iconGold,
};

export function StatCard({
  title,
  value,
  trend,
  trendUp,
  icon: Icon,
  colorClass,
}: StatCardProps) {
  return (
    <div className={`${styles.card} glass`}>
      <div className={styles.top}>
        <div className={styles.iconWrap}>
          <Icon className={`${styles.icon} ${iconColorMap[colorClass]}`} />
        </div>
        <div className={`${styles.trend} ${trendUp ? styles.trendUp : styles.trendDown}`}>
          <span dir="ltr">{trend}</span>
          {trendUp ? (
            <ArrowUpRight className={styles.trendIcon} />
          ) : (
            <ArrowDownRight className={styles.trendIcon} />
          )}
        </div>
      </div>
      <div className={styles.body}>
        <h3 className={styles.label}>{title}</h3>
        <div className={`${styles.value} tnum`}>{value}</div>
      </div>
    </div>
  );
}

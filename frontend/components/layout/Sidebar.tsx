'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  PenTool,
  TrendingUp,
  MessageSquare,
  Network,
} from 'lucide-react';
import styles from './Sidebar.module.css';

const navItems = [
  { path: '/dashboard', label: 'داشبورد', icon: LayoutDashboard, colorKey: null },
  { path: '/content-agent', label: 'عامل محتوا', icon: PenTool, colorKey: 'content' },
  { path: '/sales-agent', label: 'عامل فروش', icon: TrendingUp, colorKey: 'sales' },
  { path: '/support-agent', label: 'عامل پشتیبانی', icon: MessageSquare, colorKey: 'support' },
  { path: '/coordinator-agent', label: 'عامل هماهنگ‌کننده', icon: Network, colorKey: 'coordinator' },
] as const;

const iconColorMap = {
  content: styles.navIconContent,
  sales: styles.navIconSales,
  support: styles.navIconSupport,
  coordinator: styles.navIconCoordinator,
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.logo}>
          <Network className={styles.logoIcon} />
        </div>
        <h1 className={styles.title}>مدیریت هوشمند</h1>
      </div>

      <nav className={styles.nav}>
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.path);
          const Icon = item.icon;
          const iconClass = isActive
            ? item.colorKey
              ? iconColorMap[item.colorKey]
              : styles.navIconActive
            : styles.navIcon;

          return (
            <Link
              key={item.path}
              href={item.path}
              className={`${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
            >
              <Icon className={iconClass} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className={styles.footer}>
        <div className={styles.user}>
          <div className={styles.avatar}>
            <img
              src="https://i.pravatar.cc/150?img=32"
              alt="Admin"
              className={styles.avatarImg}
            />
          </div>
          <div>
            <div className={styles.userName}>سارا احمدی</div>
            <div className={styles.userRole}>مدیر فروشگاه</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

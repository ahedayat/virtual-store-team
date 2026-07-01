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
import styles from './MobileNav.module.css';

const navItems = [
  { path: '/dashboard', label: 'داشبورد', icon: LayoutDashboard },
  { path: '/content-agent', label: 'محتوا', icon: PenTool },
  { path: '/sales-agent', label: 'فروش', icon: TrendingUp },
  { path: '/support-agent', label: 'پشتیبانی', icon: MessageSquare },
  { path: '/coordinator-agent', label: 'مدیرعامل', icon: Network },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className={styles.mobileNav}>
      <div className={styles.inner}>
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.path);
          const Icon = item.icon;

          return (
            <Link
              key={item.path}
              href={item.path}
              className={`${styles.link} ${isActive ? styles.linkActive : ''}`}
            >
              <Icon className={`${styles.icon} ${isActive ? styles.iconActive : ''}`} />
              <span className={styles.label}>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

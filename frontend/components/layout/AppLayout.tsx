import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';
import { TopBar } from './TopBar';
import styles from './AppLayout.module.css';

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.layout}>
      <Sidebar />
      <div className={styles.mainColumn}>
        <div className={`${styles.aurora} aurora`} />
        <TopBar />
        <main className={styles.main}>{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}

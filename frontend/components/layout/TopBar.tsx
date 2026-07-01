import { Bell, Network, Search } from 'lucide-react';
import styles from './TopBar.module.css';

export function TopBar() {
  return (
    <header className={styles.topBar}>
      <div className={styles.mobileBrand}>
        <div className={styles.logo}>
          <Network className={styles.logoIcon} />
        </div>
        <h1 className={styles.mobileTitle}>مدیریت هوشمند</h1>
      </div>

      <div className={styles.searchWrap}>
        <Search className={styles.searchIcon} />
        <input
          type="text"
          placeholder="جستجو در محصولات، مشتریان و..."
          className={styles.searchInput}
        />
      </div>

      <div className={styles.actions}>
        <button type="button" className={styles.bellBtn} aria-label="اعلان‌ها">
          <Bell className={styles.bellIcon} />
          <span className={styles.bellDot} />
        </button>
      </div>
    </header>
  );
}

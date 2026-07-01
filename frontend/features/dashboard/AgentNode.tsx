import type { LucideIcon } from 'lucide-react';
import styles from './AgentNode.module.css';

type AgentColor = 'content' | 'sales' | 'support' | 'coordinator';

type AgentNodeProps = {
  icon: LucideIcon;
  label: string;
  color: AgentColor;
  isActive: boolean;
  position: 'center' | 'top' | 'bottomRight' | 'bottomLeft';
};

const positionMap = {
  center: styles.center,
  top: styles.top,
  bottomRight: styles.bottomRight,
  bottomLeft: styles.bottomLeft,
};

const iconColorMap = {
  content: styles.iconContent,
  sales: styles.iconSales,
  support: styles.iconSupport,
  coordinator: styles.iconCoordinator,
};

const pulseMap = {
  content: styles.pulseContent,
  sales: styles.pulseSales,
  support: styles.pulseSupport,
  coordinator: styles.pulseCoordinator,
};

export function AgentNode({
  icon: Icon,
  label,
  color,
  isActive,
  position,
}: AgentNodeProps) {
  return (
    <div className={`${styles.node} ${positionMap[position]}`}>
      <div
        className={`${styles.iconWrap} ${isActive ? styles.iconWrapActive : ''}`}
      >
        {isActive && (
          <div className={`${styles.pulse} ${pulseMap[color]}`} />
        )}
        <Icon className={`${styles.icon} ${iconColorMap[color]}`} />
      </div>
      <div className={`${styles.label} glass`}>{label}</div>
    </div>
  );
}

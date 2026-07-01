'use client';

import { useEffect, useRef } from 'react';
import {
  MessageSquare,
  Sparkles,
  Send,
  Clock,
  CheckCircle2,
  ChevronRight,
  Search,
} from 'lucide-react';

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
    </svg>
  );
}
import { useCustomers } from '@/hooks/use-customers';
import { useSupportStore } from '@/stores/support-store';
import type { Customer } from '@/types/support';
import styles from './SupportAgentPage.module.css';

export function SupportAgentPage() {
  const { data: customers, isLoading, isError } = useCustomers();
  const activeCustomer = useSupportStore((s) => s.activeCustomer);
  const messages = useSupportStore((s) => s.messages);
  const replyText = useSupportStore((s) => s.replyText);
  const isGenerating = useSupportStore((s) => s.isGenerating);
  const showMobileList = useSupportStore((s) => s.showMobileList);
  const setActiveCustomer = useSupportStore((s) => s.setActiveCustomer);
  const addMessage = useSupportStore((s) => s.addMessage);
  const setReplyText = useSupportStore((s) => s.setReplyText);
  const setIsGenerating = useSupportStore((s) => s.setIsGenerating);
  const setShowMobileList = useSupportStore((s) => s.setShowMobileList);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleGenerateReply = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setReplyText(
        'سلام سارا عزیز وقتتون بخیر 🌸\nبله، کیف مدل لونا در رنگ‌های مشکی، عسلی و زرشکی موجود هست. رنگ مشکی رو می‌تونید از طریق لینک سایت که در بیو قرار داره سفارش بدید. اگر سوال دیگه‌ای هست در خدمتم.',
      );
      setIsGenerating(false);
    }, 1500);
  };

  const handleSend = () => {
    if (!replyText.trim()) return;
    addMessage({
      id: Date.now(),
      sender: 'admin',
      text: replyText,
      time: new Date().toLocaleTimeString('fa-IR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    });
    setReplyText('');
  };

  const handleSelectCustomer = (customer: Customer) => {
    setActiveCustomer(customer);
    setShowMobileList(false);
  };

  if (isLoading) {
    return <div className={styles.loading}>در حال بارگذاری...</div>;
  }

  if (isError || !customers) {
    return <div className={styles.error}>خطا در بارگذاری مشتریان</div>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.mobileHeader}>
        <div className={styles.mobileHeaderLeft}>
          <button
            type="button"
            onClick={() => setShowMobileList(true)}
            className={styles.mobileBackBtn}
          >
            <ChevronRight className={styles.mobileBackIcon} />
          </button>
          <div className={styles.mobileUser}>
            <img
              src={activeCustomer.avatar}
              alt=""
              className={styles.mobileAvatar}
            />
            <div>
              <div className={styles.mobileName}>{activeCustomer.name}</div>
              <div className={styles.mobileUsername}>
                <InstagramIcon className={styles.instaIconSm} />{' '}
                {activeCustomer.username}
              </div>
            </div>
          </div>
        </div>
        <div className={styles.mobileAgentIcon}>
          <MessageSquare className={styles.mobileAgentIconSvg} />
        </div>
      </div>

      <div
        className={`${styles.sidebar} ${showMobileList ? styles.sidebarOpen : ''}`}
      >
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarTitleRow}>
            <h2 className={styles.sidebarTitle}>
              <MessageSquare className={styles.sidebarTitleIcon} />
              پیام‌های پشتیبانی
            </h2>
            <button
              type="button"
              className={styles.sidebarCloseBtn}
              onClick={() => setShowMobileList(false)}
            >
              <ChevronRight className={styles.sidebarCloseIcon} />
            </button>
          </div>
          <div className={styles.searchWrap}>
            <Search className={styles.searchIcon} />
            <input
              type="text"
              placeholder="جستجو..."
              className={styles.searchInput}
            />
          </div>
        </div>

        <div className={styles.customerList}>
          {customers.map((customer) => (
            <button
              key={customer.id}
              type="button"
              onClick={() => handleSelectCustomer(customer)}
              className={`${styles.customerBtn} ${activeCustomer.id === customer.id ? styles.customerBtnActive : ''}`}
            >
              <div className={styles.avatarWrap}>
                <img
                  src={customer.avatar}
                  alt=""
                  className={styles.customerAvatar}
                />
                <div className={styles.instaBadge}>
                  <InstagramIcon className={styles.instaBadgeIcon} />
                </div>
              </div>
              <div className={styles.customerInfo}>
                <div className={styles.customerTop}>
                  <span className={styles.customerName}>{customer.name}</span>
                  <span className={styles.customerTime}>{customer.time}</span>
                </div>
                <div className={styles.customerMsg}>{customer.lastMsg}</div>
              </div>
              {customer.unread > 0 && (
                <div className={styles.unreadBadge}>{customer.unread}</div>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.chatArea}>
        <div className={styles.chatOverlay} />

        <div className={`${styles.desktopHeader} glass`}>
          <div className={styles.desktopUser}>
            <img
              src={activeCustomer.avatar}
              alt=""
              className={styles.desktopAvatar}
            />
            <div>
              <div className={styles.desktopName}>{activeCustomer.name}</div>
              <div className={styles.desktopUsername}>
                <InstagramIcon className={styles.instaIconSm} />{' '}
                {activeCustomer.username}
              </div>
            </div>
          </div>
          <div className={styles.agentBadge}>
            <span className={styles.agentDot} />
            عامل پشتیبانی فعال
          </div>
        </div>

        <div className={styles.messages}>
          <div className={styles.todayLabel}>امروز</div>

          {messages.map((msg) => {
            const isCustomer = msg.sender === 'customer';
            return (
              <div
                key={msg.id}
                className={`${styles.msgRow} ${isCustomer ? styles.msgRowCustomer : styles.msgRowAdmin}`}
              >
                <div
                  className={`${styles.bubble} ${isCustomer ? styles.bubbleCustomer : styles.bubbleAdmin}`}
                >
                  <div className={styles.msgText}>{msg.text}</div>
                  <div
                    className={`${styles.msgTime} ${isCustomer ? styles.msgTimeCustomer : styles.msgTimeAdmin}`}
                  >
                    {msg.time}
                    {!isCustomer && (
                      <CheckCircle2 className={styles.checkIcon} />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <div className={`${styles.composer} pbSafe`}>
          <div className={styles.composerInner}>
            <div className={styles.composerHint}>
              <Clock className={styles.hintIcon} /> پاسخ هوشمند فقط پیش‌نویس
              است و بدون تایید شما ارسال نمی‌شود.
            </div>

            <div className={styles.composerBox}>
              <textarea
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="پاسخ خود را بنویسید..."
                className={styles.replyTextarea}
                dir="rtl"
              />

              <div className={styles.composerActions}>
                <button
                  type="button"
                  onClick={handleGenerateReply}
                  disabled={isGenerating}
                  className={styles.generateBtn}
                >
                  {isGenerating ? (
                    <span className={styles.spinner} />
                  ) : (
                    <Sparkles className={styles.generateIcon} />
                  )}
                  تولید پاسخ هوشمند
                </button>

                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!replyText.trim()}
                  className={`${styles.sendBtn} ${replyText.trim() ? styles.sendBtnActive : styles.sendBtnDisabled}`}
                >
                  <Send className={styles.sendIcon} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

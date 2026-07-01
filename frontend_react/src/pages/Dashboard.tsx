import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Network,
  PenTool,
  TrendingUp,
  MessageSquare,
  CheckCircle2,
  Clock,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  ChevronLeft } from
'lucide-react';
const AgentNode = ({
  icon: Icon,
  label,
  colorClass,
  isActive,
  position






}: {icon: any;label: string;colorClass: string;isActive: boolean;position: string;}) => {
  return (
    <div
      className={`absolute ${position} flex flex-col items-center gap-3 z-10`}>
      
      <div
        className={`relative flex items-center justify-center w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-surface shadow-lift border border-champagne transition-all duration-500 ${isActive ? 'scale-110' : ''}`}>
        
        {isActive &&
        <div
          className={`absolute inset-0 rounded-2xl opacity-20 animate-[agentPulse_2s_ease-in-out_infinite] ${colorClass.replace('text-', 'bg-')}`}>
        </div>
        }
        <Icon className={`w-8 h-8 md:w-10 md:h-10 ${colorClass}`} />
      </div>
      <div className="glass px-3 py-1.5 rounded-full text-xs md:text-sm font-medium shadow-sm border border-champagne/50">
        {label}
      </div>
    </div>);

};
const StatCard = ({
  title,
  value,
  trend,
  trendUp,
  icon: Icon,
  colorClass
}: any) =>
<div className="glass rounded-2xl p-5 border border-champagne/50 shadow-soft hover:shadow-lift transition-shadow">
    <div className="flex justify-between items-start mb-4">
      <div className={`p-2.5 rounded-xl bg-surface shadow-sm ${colorClass}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div
      className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${trendUp ? 'text-agent-sales bg-agent-sales/10' : 'text-agent-content bg-agent-content/10'}`}>
      
        <span dir="ltr">{trend}</span>
        {trendUp ?
      <ArrowUpRight className="w-3 h-3" /> :

      <ArrowDownRight className="w-3 h-3" />
      }
      </div>
    </div>
    <div className="space-y-1">
      <h3 className="text-muted text-sm font-medium">{title}</h3>
      <div className="text-2xl font-bold text-ink tnum">{value}</div>
    </div>
  </div>;

export function Dashboard() {
  const [activeAgent, setActiveAgent] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveAgent((prev) => (prev + 1) % 4);
    }, 3000);
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-ink mb-2">
            داشبورد مدیریت
          </h1>
          <p className="text-muted">
            نمای کلی وضعیت فروشگاه و فعالیت عامل‌های هوشمند
          </p>
        </div>
        <div className="glass px-4 py-2 rounded-xl border border-champagne/50 flex items-center gap-2 text-sm font-medium text-ink shadow-sm">
          <span className="w-2 h-2 rounded-full bg-agent-sales animate-pulse"></span>
          سیستم در وضعیت مطلوب
        </div>
      </div>

      {/* Constellation Area */}
      <div className="relative w-full h-[340px] md:h-[400px] glass rounded-3xl border border-champagne overflow-hidden flex items-center justify-center shadow-soft">
        {/* SVG Connections */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{
            filter: 'drop-shadow(0 0 8px rgba(211,154,44,0.2))'
          }}>
          
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
            className="animate-[dashFlow_20s_linear_infinite]">
            
            {/* Center to Top (Content) */}
            <path d="M 50% 50% L 50% 20%" />
            {/* Center to Bottom Right (Sales) */}
            <path d="M 50% 50% L 75% 75%" />
            {/* Center to Bottom Left (Support) */}
            <path d="M 50% 50% L 25% 75%" />
          </g>
        </svg>

        {/* Center Node */}
        <AgentNode
          icon={Network}
          label="عامل هماهنگ‌کننده"
          colorClass="text-agent-coordinator"
          isActive={activeAgent === 0}
          position="top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
        

        {/* Top Node */}
        <AgentNode
          icon={PenTool}
          label="عامل محتوا"
          colorClass="text-agent-content"
          isActive={activeAgent === 1}
          position="top-[10%] md:top-[15%] left-1/2 -translate-x-1/2" />
        

        {/* Bottom Right Node */}
        <AgentNode
          icon={TrendingUp}
          label="عامل فروش"
          colorClass="text-agent-sales"
          isActive={activeAgent === 2}
          position="bottom-[15%] md:bottom-[20%] right-[15%] md:right-[25%]" />
        

        {/* Bottom Left Node */}
        <AgentNode
          icon={MessageSquare}
          label="عامل پشتیبانی"
          colorClass="text-agent-support"
          isActive={activeAgent === 3}
          position="bottom-[15%] md:bottom-[20%] left-[15%] md:left-[25%]" />
        
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          title="کارهای در انتظار"
          value="۱۲"
          trend="۴+"
          trendUp={false}
          icon={Clock}
          colorClass="text-agent-coordinator" />
        
        <StatCard
          title="پیام‌های پشتیبانی"
          value="۵"
          trend="۲-"
          trendUp={true}
          icon={MessageSquare}
          colorClass="text-agent-support" />
        
        <StatCard
          title="پیشنهادهای فروش"
          value="۸"
          trend="۳+"
          trendUp={true}
          icon={TrendingUp}
          colorClass="text-agent-sales" />
        
        <StatCard
          title="محتوای آماده"
          value="۴"
          trend="۱+"
          trendUp={true}
          icon={PenTool}
          colorClass="text-agent-content" />
        
        <StatCard
          title="فروش امروز"
          value="۱۲.۵M"
          trend="۱۵٪+"
          trendUp={true}
          icon={CheckCircle2}
          colorClass="text-gold" />
        
        <StatCard
          title="وضعیت کلی"
          value="عالی"
          trend="پایدار"
          trendUp={true}
          icon={AlertCircle}
          colorClass="text-agent-sales" />
        
      </div>

      {/* Priority Queue & Activity */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Priority Queue */}
        <div className="glass rounded-3xl p-6 border border-champagne shadow-soft">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-ink">
              اقدامات نیازمند بررسی
            </h2>
            <Link
              to="/coordinator-agent"
              className="text-sm text-gold hover:text-gold-soft font-medium flex items-center gap-1">
              
              مشاهده همه <ChevronLeft className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-4">
            {[
            {
              title: 'تایید کپشن کالکشن پاییزه',
              agent: 'محتوا',
              time: '۱۰ دقیقه پیش',
              color: 'bg-agent-content/10 text-agent-content',
              path: '/content-agent'
            },
            {
              title: 'پیشنهاد تخفیف کیف چرم دستی',
              agent: 'فروش',
              time: '۱ ساعت پیش',
              color: 'bg-agent-sales/10 text-agent-sales',
              path: '/sales-agent'
            },
            {
              title: 'پاسخ به سوال موجودی انبار',
              agent: 'پشتیبانی',
              time: '۲ ساعت پیش',
              color: 'bg-agent-support/10 text-agent-support',
              path: '/support-agent'
            }].
            map((item, i) =>
            <Link
              key={i}
              to={item.path}
              className="flex items-center justify-between p-4 rounded-2xl bg-surface border border-champagne/50 hover:border-gold/30 hover:shadow-sm transition-all group">
              
                <div className="flex items-center gap-4">
                  <div
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold ${item.color}`}>
                  
                    {item.agent}
                  </div>
                  <div>
                    <div className="font-medium text-ink group-hover:text-gold transition-colors">
                      {item.title}
                    </div>
                    <div className="text-xs text-muted mt-1">{item.time}</div>
                  </div>
                </div>
                <ChevronLeft className="w-5 h-5 text-champagne group-hover:text-gold transition-colors" />
              </Link>
            )}
          </div>
        </div>

        {/* Coordinator Summary */}
        <div className="glass rounded-3xl p-6 border border-champagne shadow-soft relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-agent-coordinator/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
          <div className="flex items-center gap-3 mb-6 relative z-10">
            <div className="p-2.5 rounded-xl bg-agent-coordinator/10 text-agent-coordinator">
              <Network className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-ink">خلاصه وضعیت امروز</h2>
              <p className="text-sm text-muted">گزارش عامل هماهنگ‌کننده</p>
            </div>
          </div>

          <div className="space-y-4 relative z-10">
            <p className="text-ink leading-relaxed">
              روز خوبی را سپری می‌کنیم. فروش امروز ۱۵٪ نسبت به میانگین هفته
              گذشته افزایش داشته است. عامل فروش ۳ پیشنهاد جدید برای جلوگیری از
              اتمام موجودی کالاهای پرفروش آماده کرده است.
            </p>
            <div className="p-4 rounded-2xl bg-surface border border-champagne/50">
              <div className="flex items-center gap-2 text-sm font-medium text-ink mb-2">
                <AlertCircle className="w-4 h-4 text-agent-coordinator" />
                توصیه اصلی امروز
              </div>
              <p className="text-sm text-muted leading-relaxed">
                لطفا کپشن‌های آماده شده برای کمپین آخر هفته را بررسی کنید تا در
                زمان مناسب منتشر شوند. همچنین ۲ پیام پشتیبانی نیازمند تایید
                نهایی شماست.
              </p>
            </div>
            <Link
              to="/coordinator-agent"
              className="w-full py-3 rounded-xl bg-ink text-white font-medium flex items-center justify-center gap-2 hover:bg-ink/90 transition-colors">
              
              دریافت گزارش کامل
            </Link>
          </div>
        </div>
      </div>
    </div>);

}
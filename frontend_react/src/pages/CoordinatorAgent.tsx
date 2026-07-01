import React, { useState } from 'react';
import {
  Network,
  PenTool,
  TrendingUp,
  MessageSquare,
  RefreshCw,
  FileText,
  CheckCircle2,
  AlertCircle,
  ArrowLeft,
  BarChart3,
  Clock } from
'lucide-react';
export function CoordinatorAgent() {
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastUpdate, setLastUpdate] = useState('امروز، ۰۸:۳۰ صبح');
  const handleGenerateReport = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setLastUpdate(
        `امروز، ${new Date().toLocaleTimeString('fa-IR', {
          hour: '2-digit',
          minute: '2-digit'
        })}`
      );
    }, 3000);
  };
  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500 pb-24">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 glass p-6 md:p-8 rounded-3xl border border-champagne shadow-soft relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-agent-coordinator/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 pointer-events-none"></div>

        <div className="flex items-center gap-5 relative z-10">
          <div className="w-16 h-16 rounded-2xl bg-agent-coordinator/10 flex items-center justify-center border border-agent-coordinator/20 shadow-sm">
            <Network className="w-8 h-8 text-agent-coordinator" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-ink flex items-center gap-2 mb-1">
              عامل هماهنگ‌کننده
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-agent-coordinator opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-agent-coordinator"></span>
              </span>
            </h1>
            <p className="text-muted text-sm md:text-base">
              نمای کلی وضعیت فروشگاه و هماهنگی بین عامل‌ها
            </p>
          </div>
        </div>

        <button
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className={`relative z-10 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium transition-all shadow-sm ${isGenerating ? 'bg-champagne text-muted cursor-not-allowed' : 'bg-ink text-white hover:bg-ink/90 hover:-translate-y-0.5'}`}>
          
          <RefreshCw
            className={`w-5 h-5 ${isGenerating ? 'animate-spin' : ''}`} />
          
          {isGenerating ? 'در حال تحلیل داده‌ها...' : 'دریافت گزارش جدید'}
        </button>
      </div>

      {/* Agents Status Overview */}
      <div className="grid md:grid-cols-3 gap-4">
        {[
        {
          name: 'عامل محتوا',
          icon: PenTool,
          color: 'text-agent-content',
          bg: 'bg-agent-content/10',
          border: 'border-agent-content/20',
          status: 'در انتظار بررسی',
          statusColor: 'text-orange-600 bg-orange-50',
          items: '۴ مورد'
        },
        {
          name: 'عامل فروش',
          icon: TrendingUp,
          color: 'text-agent-sales',
          bg: 'bg-agent-sales/10',
          border: 'border-agent-sales/20',
          status: 'فعال',
          statusColor: 'text-green-600 bg-green-50',
          items: '۸ پیشنهاد'
        },
        {
          name: 'عامل پشتیبانی',
          icon: MessageSquare,
          color: 'text-agent-support',
          bg: 'bg-agent-support/10',
          border: 'border-agent-support/20',
          status: 'بدون مورد فوری',
          statusColor: 'text-blue-600 bg-blue-50',
          items: 'پاسخگو'
        }].
        map((agent, i) =>
        <div
          key={i}
          className="glass p-5 rounded-2xl border border-champagne shadow-sm flex items-center justify-between">
          
            <div className="flex items-center gap-3">
              <div
              className={`p-2.5 rounded-xl ${agent.bg} ${agent.color} border ${agent.border}`}>
              
                <agent.icon className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-sm text-ink mb-1">
                  {agent.name}
                </div>
                <div
                className={`text-[10px] font-bold px-2 py-0.5 rounded-md inline-block ${agent.statusColor}`}>
                
                  {agent.status}
                </div>
              </div>
            </div>
            <div className="text-xs font-bold text-muted bg-surface px-2 py-1 rounded-lg border border-champagne/50">
              {agent.items}
            </div>
          </div>
        )}
      </div>

      {/* Daily Report */}
      <div className="glass rounded-3xl border border-champagne shadow-soft overflow-hidden relative">
        {isGenerating &&
        <div className="absolute inset-0 z-20 bg-surface/80 backdrop-blur-sm flex flex-col items-center justify-center">
            <div className="w-16 h-16 relative mb-4">
              <div className="absolute inset-0 rounded-full border-4 border-champagne"></div>
              <div className="absolute inset-0 rounded-full border-4 border-agent-coordinator border-t-transparent animate-spin"></div>
              <Network className="absolute inset-0 m-auto w-6 h-6 text-agent-coordinator animate-pulse" />
            </div>
            <div className="text-lg font-bold text-ink mb-1">
              در حال تحلیل داده‌های فروشگاه...
            </div>
            <div className="text-sm text-muted">
              ارتباط با عامل‌ها و استخراج گزارش
            </div>
          </div>
        }

        <div className="p-6 md:p-8 border-b border-champagne/50 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-agent-coordinator/10 rounded-lg">
              <FileText className="w-6 h-6 text-agent-coordinator" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-ink">
                گزارش روزانه فروشگاه
              </h2>
              <div className="text-xs text-muted mt-1 flex items-center gap-1">
                <Clock className="w-3 h-3" /> آخرین بروزرسانی: {lastUpdate}
              </div>
            </div>
          </div>
          <div className="px-4 py-2 rounded-xl bg-green-50 border border-green-100 text-green-700 text-sm font-bold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            وضعیت کلی: مطلوب
          </div>
        </div>

        <div className="p-6 md:p-8 grid md:grid-cols-2 gap-8">
          {/* Left Col */}
          <div className="space-y-8">
            <section>
              <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4" /> خلاصه فروش
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 rounded-2xl bg-surface border border-champagne/50">
                  <div className="text-xs text-muted mb-1">فروش امروز</div>
                  <div className="text-xl font-bold text-ink tnum">
                    ۱۲,۵۰۰,۰۰۰{' '}
                    <span className="text-xs font-normal">تومان</span>
                  </div>
                </div>
                <div className="p-4 rounded-2xl bg-surface border border-champagne/50">
                  <div className="text-xs text-muted mb-1">سفارشات موفق</div>
                  <div className="text-xl font-bold text-ink tnum">
                    ۱۸ <span className="text-xs font-normal">عدد</span>
                  </div>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> اقدامات پیشنهادی امروز
              </h3>
              <div className="space-y-3">
                {[
                {
                  text: 'تایید ۲ کپشن اینستاگرام برای انتشار عصر',
                  agent: 'محتوا'
                },
                {
                  text: 'بررسی پیشنهاد شارژ موجودی کیف لونا',
                  agent: 'فروش'
                },
                {
                  text: 'ارسال کد تخفیف برای ۳ سبد خرید رها شده',
                  agent: 'فروش'
                }].
                map((action, i) =>
                <div
                  key={i}
                  className="flex items-start gap-3 p-3 rounded-xl bg-champagne/30 border border-champagne/50">
                  
                    <div className="w-1.5 h-1.5 rounded-full bg-agent-coordinator mt-2 shrink-0"></div>
                    <div className="flex-1 text-sm text-ink leading-relaxed">
                      {action.text}
                    </div>
                    <div className="text-[10px] font-bold text-muted bg-surface px-2 py-1 rounded-md border border-champagne shrink-0">
                      {action.agent}
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* Right Col */}
          <div className="space-y-6">
            <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">
              وضعیت دپارتمان‌ها
            </h3>

            <div className="p-4 rounded-2xl bg-surface border border-champagne/50 flex gap-4">
              <div className="p-3 rounded-xl bg-agent-content/10 text-agent-content shrink-0 h-fit">
                <PenTool className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-ink mb-1">وضعیت محتوا</div>
                <p className="text-sm text-muted leading-relaxed">
                  ۲ کپشن و ۲ توضیحات محصول آماده بررسی است. تقویم محتوایی این
                  هفته کامل شده است.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-surface border border-champagne/50 flex gap-4">
              <div className="p-3 rounded-xl bg-agent-sales/10 text-agent-sales shrink-0 h-fit">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-ink mb-1">
                  وضعیت پیشنهادهای فروش
                </div>
                <p className="text-sm text-muted leading-relaxed">
                  ۸ پیشنهاد فعال وجود دارد. اجرای پیشنهاد تخفیف زماندار می‌تواند
                  فروش آخر هفته را ۲۰٪ افزایش دهد.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-surface border border-champagne/50 flex gap-4">
              <div className="p-3 rounded-xl bg-agent-support/10 text-agent-support shrink-0 h-fit">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-ink mb-1">وضعیت پشتیبانی</div>
                <p className="text-sm text-muted leading-relaxed">
                  میانگین زمان پاسخگویی به زیر ۱۰ دقیقه کاهش یافته است. ۵ پیام
                  در انتظار تایید نهایی شماست.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>);

}
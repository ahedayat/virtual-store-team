import React, { useState } from 'react';
import {
  TrendingUp,
  Package,
  Tag,
  Clock,
  Users,
  UserPlus,
  MessageCircle,
  Edit3,
  Save,
  X,
  Check,
  Sparkles } from
'lucide-react';
type RecType =
'همه' |
'شارژ' |
'تخفیف کالا' |
'تخفیف زماندار' |
'کوپن عمومی' |
'کوپن فردی' |
'پیگیری';
const mockRecommendations = [
{
  id: 1,
  type: 'شارژ',
  priority: 5,
  title: 'نیاز فوری به شارژ موجودی',
  description: 'موجودی کیف چرم مدل لونا رو به اتمام است و تقاضا بالاست.',
  reason:
  'در هفته گذشته روزانه ۳ عدد فروش داشته‌ایم. موجودی فعلی فقط برای ۲ روز آینده کافیست.',
  payload: {
    محصول: 'کیف چرم کراس‌بادی مدل لونا',
    'موجودی فعلی': '۵ عدد',
    'مقدار پیشنهادی شارژ': '۵۰ عدد',
    'ضرر احتمالی جلوگیری‌شده': '۱۲,۵۰۰,۰۰۰ تومان'
  }
},
{
  id: 2,
  type: 'تخفیف زماندار',
  priority: 4,
  title: 'فروش ویژه آخر هفته',
  description: 'پیشنهاد تخفیف برای کالکشن تابستانه جهت تخلیه انبار.',
  reason: 'با توجه به نزدیک شدن به فصل پاییز، فروش این اقلام کاهش یافته است.',
  payload: {
    محصولات: 'کالکشن تابستانه (۴ قلم)',
    'زمان شروع': 'پنجشنبه ۰۸:۰۰',
    'زمان پایان': 'جمعه ۲۳:۵۹',
    'درصد تخفیف': '۲۵٪'
  }
},
{
  id: 3,
  type: 'پیگیری',
  priority: 3,
  title: 'پیگیری سبد خرید رها شده',
  description: 'مشتری VIP سبد خرید با ارزش بالا را رها کرده است.',
  reason:
  'این مشتری در ۶ ماه گذشته ۳ خرید موفق داشته است. ارسال پیام یادآوری احتمال تبدیل را بالا می‌برد.',
  payload: {
    مشتری: 'مریم حسینی (@maryam_h)',
    وضعیت: 'سبد خرید رها شده',
    'ارزش احتمالی سفارش': '۴,۸۰۰,۰۰۰ تومان',
    'پیشنهاد پیگیری': 'ارسال پیام در دایرکت با کد تخفیف ۵٪'
  }
}];

const getTypeConfig = (type: string) => {
  switch (type) {
    case 'شارژ':
      return {
        icon: Package,
        color: 'text-blue-600',
        bg: 'bg-blue-50',
        border: 'border-blue-200'
      };
    case 'تخفیف کالا':
      return {
        icon: Tag,
        color: 'text-rose-600',
        bg: 'bg-rose-50',
        border: 'border-rose-200'
      };
    case 'تخفیف زماندار':
      return {
        icon: Clock,
        color: 'text-orange-600',
        bg: 'bg-orange-50',
        border: 'border-orange-200'
      };
    case 'کوپن عمومی':
      return {
        icon: Users,
        color: 'text-purple-600',
        bg: 'bg-purple-50',
        border: 'border-purple-200'
      };
    case 'کوپن فردی':
      return {
        icon: UserPlus,
        color: 'text-teal-600',
        bg: 'bg-teal-50',
        border: 'border-teal-200'
      };
    case 'پیگیری':
      return {
        icon: MessageCircle,
        color: 'text-indigo-600',
        bg: 'bg-indigo-50',
        border: 'border-indigo-200'
      };
    default:
      return {
        icon: TrendingUp,
        color: 'text-agent-sales',
        bg: 'bg-agent-sales/10',
        border: 'border-agent-sales/20'
      };
  }
};
export function SalesAgent() {
  const [filter, setFilter] = useState<RecType>('همه');
  const [items, setItems] = useState(mockRecommendations);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    title: '',
    description: '',
    reason: ''
  });
  const filteredItems = items.filter(
    (item) => filter === 'همه' || item.type === filter
  );
  const handleEditClick = (item: any) => {
    setEditingId(item.id);
    setEditForm({
      title: item.title,
      description: item.description,
      reason: item.reason
    });
  };
  const handleSave = (id: number) => {
    setItems(
      items.map((item) =>
      item.id === id ?
      {
        ...item,
        ...editForm
      } :
      item
      )
    );
    setEditingId(null);
  };
  const handleAction = (id: number, action: 'تایید' | 'انصراف') => {
    setItems(items.filter((item) => item.id !== id));
  };
  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 glass p-6 md:p-8 rounded-3xl border border-champagne shadow-soft relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-agent-sales/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 pointer-events-none"></div>

        <div className="flex items-center gap-5 relative z-10">
          <div className="w-16 h-16 rounded-2xl bg-agent-sales/10 flex items-center justify-center border border-agent-sales/20 shadow-sm">
            <TrendingUp className="w-8 h-8 text-agent-sales" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-ink flex items-center gap-2 mb-1">
              عامل فروش
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-agent-sales opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-agent-sales"></span>
              </span>
            </h1>
            <p className="text-muted text-sm md:text-base">
              پیشنهادهای هوشمند برای افزایش فروش، کاهش ضرر و پیگیری مشتریان
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 relative z-10 w-full md:w-auto">
          {[
          {
            label: 'پیشنهاد فوری',
            val: '۲',
            color: 'text-rose-600'
          },
          {
            label: 'فرصت تخفیف',
            val: '۴',
            color: 'text-orange-600'
          },
          {
            label: 'نیاز به شارژ',
            val: '۱',
            color: 'text-blue-600'
          },
          {
            label: 'قابل پیگیری',
            val: '۵',
            color: 'text-indigo-600'
          }].
          map((s, i) =>
          <div
            key={i}
            className="bg-surface/80 p-3 rounded-xl border border-champagne/50 text-center shadow-sm">
            
              <div className={`text-xl font-bold tnum mb-0.5 ${s.color}`}>
                {s.val}
              </div>
              <div className="text-[10px] font-medium text-muted">
                {s.label}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {(
        [
        'همه',
        'شارژ',
        'تخفیف کالا',
        'تخفیف زماندار',
        'کوپن عمومی',
        'کوپن فردی',
        'پیگیری'] as
        RecType[]).
        map((f) =>
        <button
          key={f}
          onClick={() => setFilter(f)}
          className={`px-5 py-2.5 rounded-full text-sm font-medium whitespace-nowrap transition-all ${filter === f ? 'bg-surface border-agent-sales/30 text-agent-sales shadow-sm border' : 'bg-transparent border-transparent text-muted hover:bg-champagne/50 border'}`}>
          
            {f}
          </button>
        )}
      </div>

      {/* Recommendations List */}
      <div className="space-y-6">
        {filteredItems.map((item) => {
          const isEditing = editingId === item.id;
          const config = getTypeConfig(item.type);
          const Icon = config.icon;
          return (
            <div
              key={item.id}
              className="glass rounded-3xl border border-champagne shadow-soft overflow-hidden flex flex-col md:flex-row">
              
              {/* Main Content Area */}
              <div className="flex-1 p-6 md:p-8 border-b md:border-b-0 md:border-l border-champagne/50">
                <div className="flex items-center justify-between mb-6">
                  <div
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold ${config.bg} ${config.color} border ${config.border}`}>
                    
                    <Icon className="w-4 h-4" />
                    {item.type}
                  </div>
                  <div className="flex items-center gap-1">
                    {[...Array(5)].map((_, i) =>
                    <div
                      key={i}
                      className={`w-1.5 h-4 rounded-full ${i < item.priority ? 'bg-agent-sales' : 'bg-champagne'}`}>
                    </div>
                    )}
                  </div>
                </div>

                {isEditing ?
                <div className="space-y-4">
                    <input
                    value={editForm.title}
                    onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      title: e.target.value
                    })
                    }
                    className="w-full text-xl font-bold text-ink bg-surface border border-champagne rounded-xl p-3 focus:outline-none focus:border-agent-sales/50" />
                  
                    <textarea
                    value={editForm.description}
                    onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      description: e.target.value
                    })
                    }
                    className="w-full text-sm text-ink bg-surface border border-champagne rounded-xl p-3 h-20 resize-none focus:outline-none focus:border-agent-sales/50" />
                  
                    <div>
                      <label className="text-xs font-bold text-ink mb-1 block">
                        دلیل پیشنهاد
                      </label>
                      <textarea
                      value={editForm.reason}
                      onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        reason: e.target.value
                      })
                      }
                      className="w-full text-sm text-ink bg-surface border border-champagne rounded-xl p-3 h-20 resize-none focus:outline-none focus:border-agent-sales/50" />
                    
                    </div>
                  </div> :

                <>
                    <h2 className="text-xl font-bold text-ink mb-2">
                      {item.title}
                    </h2>
                    <p className="text-muted text-sm leading-relaxed mb-6">
                      {item.description}
                    </p>

                    <div className="p-4 rounded-2xl bg-champagne/30 border border-champagne/50">
                      <div className="text-xs font-bold text-ink mb-2 flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-agent-sales" />
                        دلیل پیشنهاد
                      </div>
                      <p className="text-sm text-ink leading-relaxed">
                        {item.reason}
                      </p>
                    </div>
                  </>
                }
              </div>

              {/* Payload & Actions Area */}
              <div className="w-full md:w-80 bg-surface/50 flex flex-col">
                <div className="p-6 flex-1">
                  <div className="text-xs font-bold text-muted mb-4 uppercase tracking-wider">
                    جزئیات اقدام
                  </div>
                  <div className="space-y-3">
                    {Object.entries(item.payload).map(([key, value], i) =>
                    <div key={i} className="flex flex-col gap-1">
                        <span className="text-xs text-muted">{key}</span>
                        <span className="text-sm font-bold text-ink">
                          {value as string}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-4 border-t border-champagne/50 bg-surface flex flex-col gap-2">
                  {isEditing ?
                  <button
                    onClick={() => handleSave(item.id)}
                    className="w-full py-2.5 rounded-xl text-sm font-medium bg-agent-sales text-white shadow-sm hover:bg-agent-sales/90 transition-colors flex items-center justify-center gap-2">
                    
                      <Save className="w-4 h-4" /> ذخیره تغییرات
                    </button> :

                  <button
                    onClick={() => handleEditClick(item)}
                    className="w-full py-2.5 rounded-xl text-sm font-medium bg-champagne/50 text-ink hover:bg-champagne transition-colors flex items-center justify-center gap-2">
                    
                      <Edit3 className="w-4 h-4" /> ویرایش پیشنهاد
                    </button>
                  }

                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => handleAction(item.id, 'انصراف')}
                      className="flex-1 py-2.5 rounded-xl text-sm font-medium text-muted hover:bg-champagne/50 transition-colors">
                      
                      انصراف
                    </button>
                    <button
                      onClick={() => handleAction(item.id, 'تایید')}
                      className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-ink text-white shadow-sm hover:bg-ink/90 transition-colors">
                      
                      تایید اقدام
                    </button>
                  </div>
                </div>
              </div>
            </div>);

        })}
      </div>

      {filteredItems.length === 0 &&
      <div className="text-center py-20 text-muted">
          پیشنهادی در این دسته یافت نشد.
        </div>
      }
    </div>);

}
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PenTool,
  Plus,
  Check,
  X,
  Edit3,
  Save,
  Image as ImageIcon,
  AlignRight } from
'lucide-react';
type ContentType = 'همه' | 'کپشن اینستاگرام' | 'توضیحات محصول';
const mockContent = [
{
  id: 1,
  type: 'کپشن اینستاگرام',
  product: 'کیف چرم کراس‌بادی مدل لونا',
  content:
  '✨ استایل پاییزی خود را با لونا کامل کنید!\n\nطراحی مینیمال و چرم طبیعی این کیف، آن را به همراهی بی‌نقص برای روزهای شلوغ تبدیل کرده است. سبک، جادار و همیشه شیک.\n\n🛍️ برای مشاهده رنگ‌بندی و سفارش به لینک بیو مراجعه کنید.\n\n#کیف_چرم #استایل_پاییزی #کیف_زنانه #چرم_طبیعی',
  reason: 'تمرکز بر ترندهای پاییزی و نیاز مخاطب به کیف روزمره و سبک.',
  status: 'آماده بررسی'
},
{
  id: 2,
  type: 'توضیحات محصول',
  product: 'کیف دستی مجلسی مدل آتوسا',
  content:
  'کیف دستی آتوسا، تجلی ظرافت و هنر دست است. این کیف با استفاده از مرغوب‌ترین چرم گوساله و یراق‌آلات ایتالیایی ضد خش طراحی شده است. فضای داخلی آن با آستر مخمل پوشیده شده و دارای یک جیب زیپ‌دار مخفی برای اشیای ارزشمند شماست. ابعاد مناسب آن (۲۰x۱۵x۸ سانتی‌متر) این کیف را برای مهمانی‌های شبانه و رویدادهای رسمی ایده‌آل می‌سازد.',
  reason:
  'توضیحات دقیق متریال و ابعاد برای کاهش سوالات پشتیبانی و افزایش اعتماد خریدار.',
  status: 'آماده بررسی'
}];

export function ContentAgent() {
  const [filter, setFilter] = useState<ContentType>('همه');
  const [items, setItems] = useState(mockContent);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const filteredItems = items.filter(
    (item) => filter === 'همه' || item.type === filter
  );
  const handleEditClick = (item: any) => {
    setEditingId(item.id);
    setEditValue(item.content);
  };
  const handleSave = (id: number) => {
    setItems(
      items.map((item) =>
      item.id === id ?
      {
        ...item,
        content: editValue
      } :
      item
      )
    );
    setEditingId(null);
  };
  const handleAction = (id: number, action: 'تایید' | 'رد کردن') => {
    setItems(items.filter((item) => item.id !== id));
    // In a real app, this would update status and move to a different list
  };
  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass p-6 rounded-3xl border border-champagne shadow-soft relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-agent-content/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 pointer-events-none"></div>

        <div className="flex items-center gap-4 relative z-10">
          <div className="w-14 h-14 rounded-2xl bg-agent-content/10 flex items-center justify-center border border-agent-content/20 shadow-sm">
            <PenTool className="w-7 h-7 text-agent-content" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-ink flex items-center gap-2">
              عامل محتوا
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-agent-content opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-agent-content"></span>
              </span>
            </h1>
            <p className="text-muted text-sm mt-1">
              تولید هوشمند کپشن اینستاگرام و توضیحات محصول
            </p>
          </div>
        </div>

        <Link
          to="/content-agent/new-content"
          className="relative z-10 flex items-center justify-center gap-2 bg-ink text-white px-6 py-3 rounded-xl font-medium hover:bg-ink/90 transition-all shadow-lift hover:-translate-y-0.5">
          
          <Plus className="w-5 h-5" />
          محتوای جدید
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {(['همه', 'کپشن اینستاگرام', 'توضیحات محصول'] as ContentType[]).map(
          (f) =>
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-5 py-2.5 rounded-full text-sm font-medium whitespace-nowrap transition-all ${filter === f ? 'bg-surface border-agent-content/30 text-agent-content shadow-sm border' : 'bg-transparent border-transparent text-muted hover:bg-champagne/50 border'}`}>
            
              {f}
            </button>

        )}
      </div>

      {/* Content Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {filteredItems.map((item) => {
          const isInsta = item.type === 'کپشن اینستاگرام';
          const isEditing = editingId === item.id;
          const hasChanged = isEditing && editValue !== item.content;
          return (
            <div
              key={item.id}
              className="glass rounded-3xl border border-champagne shadow-soft overflow-hidden flex flex-col">
              
              {/* Card Header */}
              <div
                className={`p-4 border-b flex items-center justify-between ${isInsta ? 'bg-gradient-to-r from-pink-500/5 to-purple-500/5 border-pink-500/10' : 'bg-surface border-champagne/50'}`}>
                
                <div className="flex items-center gap-2">
                  {isInsta ?
                  <ImageIcon className="w-4 h-4 text-pink-600" /> :

                  <AlignRight className="w-4 h-4 text-agent-content" />
                  }
                  <span
                    className={`text-xs font-bold ${isInsta ? 'text-pink-700' : 'text-agent-content'}`}>
                    
                    {item.type}
                  </span>
                </div>
                <div className="px-2.5 py-1 rounded-full bg-champagne text-xs font-medium text-muted">
                  {item.status}
                </div>
              </div>

              {/* Card Body */}
              <div className="p-5 flex-1 flex flex-col gap-4">
                <div>
                  <div className="text-xs text-muted mb-1">محصول</div>
                  <div className="font-bold text-ink">{item.product}</div>
                </div>

                <div className="flex-1 flex flex-col">
                  <div className="text-xs text-muted mb-2 flex justify-between items-center">
                    <span>متن پیشنهادی</span>
                    {!isEditing &&
                    <button
                      onClick={() => handleEditClick(item)}
                      className="text-agent-content hover:text-agent-content/80 flex items-center gap-1">
                      
                        <Edit3 className="w-3 h-3" /> ویرایش
                      </button>
                    }
                  </div>

                  {isEditing ?
                  <textarea
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-full h-40 p-3 rounded-xl border border-agent-content/30 bg-surface focus:outline-none focus:ring-2 focus:ring-agent-content/20 resize-none text-sm leading-relaxed"
                    dir="rtl"
                    autoFocus /> :


                  <div
                    onClick={() => handleEditClick(item)}
                    className="p-4 rounded-xl bg-surface border border-champagne/50 text-sm leading-relaxed whitespace-pre-wrap cursor-text hover:border-agent-content/30 transition-colors flex-1">
                    
                      {item.content}
                    </div>
                  }
                </div>

                <div className="p-3 rounded-xl bg-champagne/30 border border-champagne/50">
                  <div className="text-xs font-bold text-ink mb-1">
                    دلیل پیشنهاد
                  </div>
                  <div className="text-xs text-muted leading-relaxed">
                    {item.reason}
                  </div>
                </div>
              </div>

              {/* Card Actions */}
              <div className="p-4 border-t border-champagne/50 bg-surface/50 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleAction(item.id, 'رد کردن')}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-colors flex items-center gap-1">
                  
                  <X className="w-4 h-4" /> رد کردن
                </button>

                <div className="flex items-center gap-2">
                  {isEditing ?
                  <button
                    onClick={() => handleSave(item.id)}
                    disabled={!hasChanged}
                    className={`px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-1 transition-colors ${hasChanged ? 'bg-agent-content text-white shadow-sm hover:bg-agent-content/90' : 'bg-champagne text-muted cursor-not-allowed'}`}>
                    
                      <Save className="w-4 h-4" /> ذخیره تغییرات
                    </button> :

                  <button
                    onClick={() => handleAction(item.id, 'تایید')}
                    className="px-6 py-2 rounded-xl text-sm font-medium bg-ink text-white shadow-sm hover:bg-ink/90 transition-colors flex items-center gap-1">
                    
                      <Check className="w-4 h-4" /> تایید
                    </button>
                  }
                </div>
              </div>
            </div>);

        })}
      </div>

      {filteredItems.length === 0 &&
      <div className="text-center py-20 text-muted">
          محتوایی در این دسته یافت نشد.
        </div>
      }
    </div>);

}
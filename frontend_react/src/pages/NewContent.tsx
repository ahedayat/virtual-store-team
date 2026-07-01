import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ChevronRight,
  Sparkles,
  Check,
  Image as ImageIcon,
  AlignRight,
  Settings,
  Layers } from
'lucide-react';
type ContentType = 'کپشن اینستاگرام' | 'توضیحات محصول';
type Step = 1 | 2 | 3;
const mockProducts = [
{
  id: 1,
  name: 'کیف چرم کراس‌بادی مدل لونا'
},
{
  id: 2,
  name: 'کیف دستی مجلسی مدل آتوسا'
},
{
  id: 3,
  name: 'کوله پشتی چرم مدل هرمس'
},
{
  id: 4,
  name: 'کیف پول کلاچ مدل دیانا'
}];

export function NewContent() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [type, setType] = useState<ContentType | null>(null);
  // Form State
  const [selectedProducts, setSelectedProducts] = useState<number[]>([]);
  const [campaignAngle, setCampaignAngle] = useState('');
  const [tone, setTone] = useState('لوکس و رسمی');
  const [language, setLanguage] = useState('فارسی');
  const [draftCount, setDraftCount] = useState(2);
  // Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDrafts, setGeneratedDrafts] = useState<any[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const handleGenerate = () => {
    setIsGenerating(true);
    // Simulate API call
    setTimeout(() => {
      setIsGenerating(false);
      setStep(3);
      setGeneratedDrafts([
      {
        id: 1,
        content:
        type === 'کپشن اینستاگرام' ?
        '✨ زیبایی در سادگیست.\n\nکالکشن جدید کیف‌های چرم ما با طراحی مینیمال و کیفیت بی‌نظیر، همراه همیشگی شما در لحظات خاص خواهد بود.\n\n🛍️ سفارش از طریق لینک بیو' :
        'این محصول با استفاده از بهترین نوع چرم طبیعی و یراق‌آلات وارداتی تولید شده است. طراحی ارگونومیک و فضای داخلی بهینه‌سازی شده، آن را به انتخابی هوشمندانه تبدیل کرده است.',
        reason: 'لحن لوکس و رسمی رعایت شده و تمرکز بر کیفیت متریال است.'
      },
      {
        id: 2,
        content:
        type === 'کپشن اینستاگرام' ?
        'استایلت رو با یه انتخاب خاص کامل کن! 💫\n\nکیف‌های جدیدمون رسیدن و منتظرن تا بشن بخش جدانشدنی از استایل روزمره‌ت. سبک، جادار و فوق‌العاده شیک.\n\n👇 همین الان از سایت سفارش بده' :
        'طراحی مدرن در کنار اصالت چرم طبیعی. این کیف با ابعاد استاندارد و وزن سبک، مناسب استفاده روزمره و محیط‌های کاری است. دارای دو محفظه اصلی و یک جیب زیپ‌دار داخلی.',
        reason: 'لحن کمی صمیمی‌تر برای ایجاد ارتباط بهتر با مخاطب جوان.'
      }]
      );
    }, 2000);
  };
  const handleCreate = () => {
    // In a real app, save the selected draft
    navigate('/content-agent');
  };
  const toggleProduct = (id: number) => {
    setSelectedProducts((prev) =>
    prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };
  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500 pb-32">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link
          to="/content-agent"
          className="p-2 rounded-xl hover:bg-champagne transition-colors">
          
          <ChevronRight className="w-6 h-6 text-ink" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-ink">ساخت محتوای جدید</h1>
          <p className="text-muted text-sm mt-1">
            تنظیمات تولید محتوا توسط هوش مصنوعی
          </p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-between relative mb-12 px-4">
        <div className="absolute left-8 right-8 top-1/2 -translate-y-1/2 h-0.5 bg-champagne -z-10"></div>
        <div
          className="absolute right-8 top-1/2 -translate-y-1/2 h-0.5 bg-agent-content -z-10 transition-all duration-500"
          style={{
            width: step === 1 ? '0%' : step === 2 ? '50%' : '100%'
          }}>
        </div>

        {[
        {
          num: 1,
          label: 'انتخاب نوع',
          icon: Layers
        },
        {
          num: 2,
          label: 'تنظیمات',
          icon: Settings
        },
        {
          num: 3,
          label: 'بررسی',
          icon: Sparkles
        }].
        map((s) =>
        <div key={s.num} className="flex flex-col items-center gap-2">
            <div
            className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${step >= s.num ? 'bg-agent-content border-agent-content text-white shadow-glow' : 'bg-surface border-champagne text-muted'}`}>
            
              <s.icon className="w-5 h-5" />
            </div>
            <span
            className={`text-xs font-medium ${step >= s.num ? 'text-ink' : 'text-muted'}`}>
            
              {s.label}
            </span>
          </div>
        )}
      </div>

      {/* Step 1: Type Selection */}
      {step === 1 &&
      <div className="grid md:grid-cols-2 gap-4 animate-in slide-in-from-right-8 duration-300">
          <button
          onClick={() => {
            setType('کپشن اینستاگرام');
            setStep(2);
          }}
          className="glass p-8 rounded-3xl border border-champagne hover:border-agent-content/50 hover:shadow-lift transition-all group text-right flex flex-col items-start gap-4">
          
            <div className="p-4 rounded-2xl bg-gradient-to-br from-pink-500/10 to-purple-500/10 text-pink-600 group-hover:scale-110 transition-transform">
              <ImageIcon className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-ink mb-2">
                کپشن اینستاگرام
              </h3>
              <p className="text-sm text-muted leading-relaxed">
                تولید کپشن‌های جذاب و تعاملی برای پست‌ها و ریلزهای اینستاگرام با
                هشتگ‌های مرتبط.
              </p>
            </div>
          </button>

          <button
          onClick={() => {
            setType('توضیحات محصول');
            setStep(2);
          }}
          className="glass p-8 rounded-3xl border border-champagne hover:border-agent-content/50 hover:shadow-lift transition-all group text-right flex flex-col items-start gap-4">
          
            <div className="p-4 rounded-2xl bg-agent-content/10 text-agent-content group-hover:scale-110 transition-transform">
              <AlignRight className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-ink mb-2">توضیحات محصول</h3>
              <p className="text-sm text-muted leading-relaxed">
                تولید توضیحات دقیق، سئو شده و ترغیب‌کننده برای صفحات محصول در
                وب‌سایت.
              </p>
            </div>
          </button>
        </div>
      }

      {/* Step 2: Configuration Form */}
      {step === 2 &&
      <div className="glass rounded-3xl border border-champagne p-6 md:p-8 shadow-soft animate-in slide-in-from-right-8 duration-300 space-y-8">
          <div className="flex items-center justify-between pb-4 border-b border-champagne/50">
            <h2 className="text-lg font-bold text-ink flex items-center gap-2">
              {type === 'کپشن اینستاگرام' ?
            <ImageIcon className="w-5 h-5 text-pink-600" /> :

            <AlignRight className="w-5 h-5 text-agent-content" />
            }
              تنظیمات {type}
            </h2>
            <button
            onClick={() => setStep(1)}
            className="text-sm text-muted hover:text-ink">
            
              تغییر نوع
            </button>
          </div>

          <div className="space-y-6">
            {/* Products */}
            <div className="space-y-3">
              <label className="block text-sm font-bold text-ink">
                محصول یا محصولات مرتبط
              </label>
              <div className="flex flex-wrap gap-2">
                {mockProducts.map((p) =>
              <button
                key={p.id}
                onClick={() => toggleProduct(p.id)}
                className={`px-4 py-2 rounded-xl text-sm transition-all border ${selectedProducts.includes(p.id) ? 'bg-ink text-white border-ink shadow-sm' : 'bg-surface border-champagne text-ink hover:border-muted'}`}>
                
                    {p.name}
                  </button>
              )}
              </div>
            </div>

            {/* Campaign Angle */}
            <div className="space-y-3">
              <label className="block text-sm font-bold text-ink">
                زاویه کمپین یا هدف محتوا
              </label>
              <input
              type="text"
              value={campaignAngle}
              onChange={(e) => setCampaignAngle(e.target.value)}
              placeholder="مثلا: معرفی کالکشن جدید پاییزه، تمرکز روی هدیه روز مادر..."
              className="w-full p-3.5 rounded-xl border border-champagne bg-surface focus:outline-none focus:ring-2 focus:ring-agent-content/20 focus:border-agent-content/50 transition-all text-sm" />
            
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Tone */}
              <div className="space-y-3">
                <label className="block text-sm font-bold text-ink">
                  لحن برند
                </label>
                <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full p-3.5 rounded-xl border border-champagne bg-surface focus:outline-none focus:ring-2 focus:ring-agent-content/20 focus:border-agent-content/50 transition-all text-sm appearance-none">
                
                  <option>لوکس و رسمی</option>
                  <option>صمیمی و مینیمال</option>
                  <option>هیجان‌انگیز و فروش‌محور</option>
                </select>
              </div>

              {/* Language */}
              <div className="space-y-3">
                <label className="block text-sm font-bold text-ink">
                  زبان خروجی
                </label>
                <div className="flex p-1 rounded-xl bg-champagne/50 border border-champagne">
                  {['فارسی', 'انگلیسی'].map((lang) =>
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${language === lang ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'}`}>
                  
                      {lang}
                    </button>
                )}
                </div>
              </div>
            </div>

            {/* Draft Count */}
            <div className="space-y-3">
              <label className="block text-sm font-bold text-ink">
                تعداد پیش‌نویس (Draft)
              </label>
              <div className="flex items-center gap-4">
                <input
                type="range"
                min="1"
                max="5"
                value={draftCount}
                onChange={(e) => setDraftCount(parseInt(e.target.value))}
                className="flex-1 accent-agent-content" />
              
                <span className="w-8 text-center font-bold text-ink tnum">
                  {draftCount}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-champagne/50 flex justify-end">
            <button
            onClick={handleGenerate}
            disabled={
            selectedProducts.length === 0 || !campaignAngle || isGenerating
            }
            className={`px-8 py-3.5 rounded-xl font-bold flex items-center gap-2 transition-all ${selectedProducts.length > 0 && campaignAngle && !isGenerating ? 'bg-agent-content text-white shadow-glow hover:bg-agent-content/90 hover:-translate-y-0.5' : 'bg-champagne text-muted cursor-not-allowed'}`}>
            
              {isGenerating ?
            <>
                  <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  در حال پردازش...
                </> :

            <>
                  <Sparkles className="w-5 h-5" />
                  تولید محتوای هوشمند
                </>
            }
            </button>
          </div>
        </div>
      }

      {/* Step 3: Results */}
      {step === 3 &&
      <div className="space-y-6 animate-in slide-in-from-bottom-8 duration-500">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-ink">
              پیش‌نویس‌های تولید شده
            </h2>
            <button
            onClick={() => setStep(2)}
            className="text-sm text-agent-content hover:underline">
            
              تغییر تنظیمات
            </button>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {generatedDrafts.map((draft) =>
          <div
            key={draft.id}
            onClick={() => setSelectedDraftId(draft.id)}
            className={`glass rounded-3xl p-6 border-2 transition-all cursor-pointer relative overflow-hidden ${selectedDraftId === draft.id ? 'border-agent-content shadow-glow bg-agent-content/5' : 'border-champagne hover:border-agent-content/30 shadow-soft'}`}>
            
                {selectedDraftId === draft.id &&
            <div className="absolute top-4 left-4 w-6 h-6 rounded-full bg-agent-content text-white flex items-center justify-center">
                    <Check className="w-4 h-4" />
                  </div>
            }

                <div className="text-sm leading-relaxed whitespace-pre-wrap text-ink mb-6">
                  {draft.content}
                </div>

                <div className="p-3 rounded-xl bg-surface border border-champagne/50">
                  <div className="text-xs font-bold text-ink mb-1">
                    دلیل این پیشنهاد
                  </div>
                  <div className="text-xs text-muted">{draft.reason}</div>
                </div>
              </div>
          )}
          </div>

          {/* Sticky Bottom Action */}
          <div className="fixed bottom-0 left-0 right-0 md:left-auto md:right-64 p-4 bg-surface/90 backdrop-blur-xl border-t border-champagne z-40 flex justify-end pb-safe md:pb-4">
            <button
            onClick={handleCreate}
            disabled={!selectedDraftId}
            className={`px-10 py-3.5 rounded-xl font-bold transition-all shadow-sm ${selectedDraftId ? 'bg-ink text-white hover:bg-ink/90 hover:-translate-y-0.5' : 'bg-champagne text-muted cursor-not-allowed'}`}>
            
              ایجاد و ذخیره
            </button>
          </div>
        </div>
      }
    </div>);

}
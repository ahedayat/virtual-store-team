import React, { useEffect, useState, useRef } from 'react';
import {
  MessageSquare,
  Sparkles,
  Send,
  Instagram,
  Clock,
  CheckCircle2,
  ChevronRight,
  Search } from
'lucide-react';
const mockCustomers = [
{
  id: 1,
  name: 'سارا رضایی',
  username: '@sara_rz',
  avatar: 'https://i.pravatar.cc/150?img=1',
  lastMsg: 'سلام، این کیف رنگ مشکی هم داره؟',
  time: '۱۰:۴۲',
  unread: 1
},
{
  id: 2,
  name: 'علی محمدی',
  username: '@ali_m',
  avatar: 'https://i.pravatar.cc/150?img=11',
  lastMsg: 'ممنون، سفارشم رسید.',
  time: 'دیروز',
  unread: 0
},
{
  id: 3,
  name: 'نگار کریمی',
  username: '@negar_k',
  avatar: 'https://i.pravatar.cc/150?img=5',
  lastMsg: 'هزینه ارسال چقدره؟',
  time: 'دیروز',
  unread: 0
}];

const initialMessages = [
{
  id: 1,
  sender: 'customer',
  text: 'سلام وقت بخیر',
  time: '۱۰:۴۰'
},
{
  id: 2,
  sender: 'customer',
  text: 'ببخشید این کیف مدل لونا رنگ مشکی هم داره؟',
  time: '۱۰:۴۲'
}];

export function SupportAgent() {
  const [activeCustomer, setActiveCustomer] = useState(mockCustomers[0]);
  const [messages, setMessages] = useState(initialMessages);
  const [replyText, setReplyText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showMobileList, setShowMobileList] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth'
    });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  const handleGenerateReply = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setReplyText(
        'سلام سارا عزیز وقتتون بخیر 🌸\nبله، کیف مدل لونا در رنگ‌های مشکی، عسلی و زرشکی موجود هست. رنگ مشکی رو می‌تونید از طریق لینک سایت که در بیو قرار داره سفارش بدید. اگر سوال دیگه‌ای هست در خدمتم.'
      );
      setIsGenerating(false);
    }, 1500);
  };
  const handleSend = () => {
    if (!replyText.trim()) return;
    const newMsg = {
      id: Date.now(),
      sender: 'admin',
      text: replyText,
      time: new Date().toLocaleTimeString('fa-IR', {
        hour: '2-digit',
        minute: '2-digit'
      })
    };
    setMessages([...messages, newMsg]);
    setReplyText('');
  };
  return (
    <div className="h-[calc(100vh-4rem)] md:h-full flex flex-col md:flex-row bg-ivory overflow-hidden">
      {/* Mobile Header (Shows when chat is active) */}
      <div className="md:hidden flex items-center justify-between p-4 bg-surface border-b border-champagne z-20">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowMobileList(true)}
            className="p-2 -ml-2 text-ink">
            
            <ChevronRight className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-2">
            <img
              src={activeCustomer.avatar}
              alt=""
              className="w-8 h-8 rounded-full" />
            
            <div>
              <div className="font-bold text-sm">{activeCustomer.name}</div>
              <div className="text-xs text-muted flex items-center gap-1">
                <Instagram className="w-3 h-3" /> {activeCustomer.username}
              </div>
            </div>
          </div>
        </div>
        <div className="w-8 h-8 rounded-lg bg-agent-support/10 flex items-center justify-center">
          <MessageSquare className="w-4 h-4 text-agent-support" />
        </div>
      </div>

      {/* Customer List Sidebar */}
      <div
        className={`
        fixed inset-0 z-30 bg-ivory md:relative md:z-0 md:w-80 border-l border-champagne flex flex-col transition-transform duration-300
        ${showMobileList ? 'translate-x-0' : 'translate-x-full md:translate-x-0'}
      `}>
        
        <div className="p-4 border-b border-champagne bg-surface">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-ink flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-agent-support" />
              پیام‌های پشتیبانی
            </h2>
            <button
              className="md:hidden p-2 text-ink"
              onClick={() => setShowMobileList(false)}>
              
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
          <div className="relative">
            <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="جستجو..."
              className="w-full bg-champagne/30 border border-champagne rounded-xl py-2 pr-9 pl-4 text-sm focus:outline-none focus:border-agent-support/50" />
            
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {mockCustomers.map((customer) =>
          <button
            key={customer.id}
            onClick={() => {
              setActiveCustomer(customer);
              setShowMobileList(false);
            }}
            className={`w-full p-4 flex items-start gap-3 border-b border-champagne/30 transition-colors text-right ${activeCustomer.id === customer.id ? 'bg-agent-support/5' : 'hover:bg-champagne/20'}`}>
            
              <div className="relative">
                <img
                src={customer.avatar}
                alt=""
                className="w-12 h-12 rounded-full object-cover" />
              
                <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-pink-500 rounded-full border-2 border-surface flex items-center justify-center">
                  <Instagram className="w-3 h-3 text-white" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-bold text-sm text-ink truncate">
                    {customer.name}
                  </span>
                  <span className="text-xs text-muted whitespace-nowrap">
                    {customer.time}
                  </span>
                </div>
                <div className="text-xs text-muted truncate">
                  {customer.lastMsg}
                </div>
              </div>
              {customer.unread > 0 &&
            <div className="w-5 h-5 rounded-full bg-agent-support text-white text-[10px] flex items-center justify-center font-bold mt-1">
                  {customer.unread}
                </div>
            }
            </button>
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-fixed relative">
        <div className="absolute inset-0 bg-ivory/95"></div>

        {/* Desktop Header */}
        <div className="hidden md:flex items-center justify-between p-4 bg-surface/80 backdrop-blur-md border-b border-champagne relative z-10">
          <div className="flex items-center gap-3">
            <img
              src={activeCustomer.avatar}
              alt=""
              className="w-10 h-10 rounded-full" />
            
            <div>
              <div className="font-bold text-ink">{activeCustomer.name}</div>
              <div className="text-xs text-muted flex items-center gap-1">
                <Instagram className="w-3 h-3" /> {activeCustomer.username}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-agent-support/10 text-agent-support text-xs font-bold border border-agent-support/20">
            <span className="w-2 h-2 rounded-full bg-agent-support animate-pulse"></span>
            عامل پشتیبانی فعال
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 relative z-10">
          <div className="text-center text-xs text-muted my-4">امروز</div>

          {messages.map((msg) => {
            const isCustomer = msg.sender === 'customer';
            return (
              <div
                key={msg.id}
                className={`flex ${isCustomer ? 'justify-start' : 'justify-end'}`}>
                
                <div
                  className={`max-w-[85%] md:max-w-[70%] rounded-2xl p-3 shadow-sm ${isCustomer ? 'bg-surface border border-champagne rounded-tr-sm' : 'bg-agent-support text-white rounded-tl-sm'}`}>
                  
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">
                    {msg.text}
                  </div>
                  <div
                    className={`text-[10px] mt-1 flex items-center gap-1 ${isCustomer ? 'text-muted' : 'text-white/70 justify-end'}`}>
                    
                    {msg.time}
                    {!isCustomer && <CheckCircle2 className="w-3 h-3" />}
                  </div>
                </div>
              </div>);

          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Reply Composer */}
        <div className="p-4 bg-surface border-t border-champagne relative z-10 pb-safe">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-2 px-1">
              <div className="text-xs text-muted flex items-center gap-1">
                <Clock className="w-3 h-3" /> پاسخ هوشمند فقط پیش‌نویس است و
                بدون تایید شما ارسال نمی‌شود.
              </div>
            </div>

            <div className="relative rounded-2xl border border-champagne bg-ivory focus-within:border-agent-support/50 focus-within:ring-1 focus-within:ring-agent-support/50 transition-all shadow-sm overflow-hidden flex flex-col">
              <textarea
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="پاسخ خود را بنویسید..."
                className="w-full p-4 bg-transparent border-none focus:outline-none resize-none min-h-[100px] text-sm leading-relaxed"
                dir="rtl" />
              

              <div className="p-2 bg-surface border-t border-champagne/50 flex items-center justify-between">
                <button
                  onClick={handleGenerateReply}
                  disabled={isGenerating}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-agent-support bg-agent-support/10 hover:bg-agent-support/20 transition-colors flex items-center gap-2">
                  
                  {isGenerating ?
                  <span className="w-4 h-4 border-2 border-agent-support/30 border-t-agent-support rounded-full animate-spin"></span> :

                  <Sparkles className="w-4 h-4" />
                  }
                  تولید پاسخ هوشمند
                </button>

                <button
                  onClick={handleSend}
                  disabled={!replyText.trim()}
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${replyText.trim() ? 'bg-agent-support text-white shadow-sm hover:bg-agent-support/90' : 'bg-champagne text-muted cursor-not-allowed'}`}>
                  
                  <Send className="w-5 h-5 -ml-1" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>);

}
import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  Link } from
'react-router-dom';
import {
  LayoutDashboard,
  PenTool,
  TrendingUp,
  MessageSquare,
  Network,
  Bell,
  Search,
  Menu } from
'lucide-react';
import { Dashboard } from './pages/Dashboard';
import { ContentAgent } from './pages/ContentAgent';
import { NewContent } from './pages/NewContent';
import { SalesAgent } from './pages/SalesAgent';
import { SupportAgent } from './pages/SupportAgent';
import { CoordinatorAgent } from './pages/CoordinatorAgent';
function Sidebar() {
  const location = useLocation();
  const navItems = [
  {
    path: '/dashboard',
    label: 'داشبورد',
    icon: LayoutDashboard
  },
  {
    path: '/content-agent',
    label: 'عامل محتوا',
    icon: PenTool,
    color: 'text-agent-content'
  },
  {
    path: '/sales-agent',
    label: 'عامل فروش',
    icon: TrendingUp,
    color: 'text-agent-sales'
  },
  {
    path: '/support-agent',
    label: 'عامل پشتیبانی',
    icon: MessageSquare,
    color: 'text-agent-support'
  },
  {
    path: '/coordinator-agent',
    label: 'عامل هماهنگ‌کننده',
    icon: Network,
    color: 'text-agent-coordinator'
  }];

  return (
    <aside className="hidden md:flex flex-col w-64 border-l border-champagne bg-surface/80 backdrop-blur-xl h-full sticky top-0">
      <div className="p-6 flex items-center gap-3 border-b border-champagne/50">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold to-brown flex items-center justify-center shadow-glow">
          <Network className="w-5 h-5 text-white" />
        </div>
        <h1 className="font-bold text-lg text-ink tracking-tight">
          مدیریت هوشمند
        </h1>
      </div>

      <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${isActive ? 'bg-ivory shadow-sm border border-champagne/50 text-ink font-medium' : 'text-muted hover:bg-ivory/50 hover:text-ink'}`}>
              
              <Icon
                className={`w-5 h-5 ${isActive ? item.color || 'text-gold' : 'text-muted group-hover:text-gold'}`} />
              
              <span>{item.label}</span>
            </Link>);

        })}
      </nav>

      <div className="p-4 border-t border-champagne/50">
        <div className="flex items-center gap-3 px-4 py-2">
          <div className="w-10 h-10 rounded-full bg-champagne overflow-hidden border-2 border-surface shadow-sm">
            <img
              src="https://i.pravatar.cc/150?img=32"
              alt="Admin"
              className="w-full h-full object-cover" />
            
          </div>
          <div>
            <div className="text-sm font-semibold text-ink">سارا احمدی</div>
            <div className="text-xs text-muted">مدیر فروشگاه</div>
          </div>
        </div>
      </div>
    </aside>);

}
function MobileNav() {
  const location = useLocation();
  const navItems = [
  {
    path: '/dashboard',
    label: 'داشبورد',
    icon: LayoutDashboard
  },
  {
    path: '/content-agent',
    label: 'محتوا',
    icon: PenTool
  },
  {
    path: '/sales-agent',
    label: 'فروش',
    icon: TrendingUp
  },
  {
    path: '/support-agent',
    label: 'پشتیبانی',
    icon: MessageSquare
  },
  {
    path: '/coordinator-agent',
    label: 'مدیرعامل',
    icon: Network
  }];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface/90 backdrop-blur-xl border-t border-champagne pb-safe z-50">
      <div className="flex justify-around items-center h-16 px-2">
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive ? 'text-gold' : 'text-muted'}`}>
              
              <Icon className={`w-5 h-5 ${isActive ? 'fill-gold/10' : ''}`} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>);

        })}
      </div>
    </nav>);

}
function TopBar() {
  return (
    <header className="h-16 border-b border-champagne/50 bg-surface/50 backdrop-blur-md sticky top-0 z-40 flex items-center justify-between px-4 md:px-8">
      <div className="flex items-center gap-4 md:hidden">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold to-brown flex items-center justify-center">
          <Network className="w-5 h-5 text-white" />
        </div>
        <h1 className="font-bold text-ink">مدیریت هوشمند</h1>
      </div>

      <div className="hidden md:flex flex-1 max-w-md relative">
        <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="text"
          placeholder="جستجو در محصولات، مشتریان و..."
          className="w-full bg-ivory border border-champagne rounded-full py-2 pr-10 pl-4 text-sm focus:outline-none focus:border-gold/50 focus:ring-1 focus:ring-gold/50 transition-all" />
        
      </div>

      <div className="flex items-center gap-3">
        <button className="w-10 h-10 rounded-full flex items-center justify-center hover:bg-champagne/50 text-muted transition-colors relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 bg-agent-content rounded-full border-2 border-surface"></span>
        </button>
      </div>
    </header>);

}
function Layout({ children }: {children: React.ReactNode;}) {
  return (
    <div
      className="flex h-screen overflow-hidden bg-ivory text-ink font-sans"
      dir="rtl">
      
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <div className="absolute inset-0 aurora pointer-events-none opacity-40"></div>
        <TopBar />
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0 relative z-10">
          {children}
        </main>
      </div>
      <MobileNav />
    </div>);

}
export function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/content-agent" element={<ContentAgent />} />
          <Route path="/content-agent/new-content" element={<NewContent />} />
          <Route path="/sales-agent" element={<SalesAgent />} />
          <Route path="/support-agent" element={<SupportAgent />} />
          <Route path="/coordinator-agent" element={<CoordinatorAgent />} />
        </Routes>
      </Layout>
    </BrowserRouter>);

}
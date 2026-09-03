import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Home,
  Zap,
  Compass,
  BarChart2,
  ListChecks,
  ShieldCheck,
  Clock,
  Menu,
  X,
  Database,
} from "lucide-react";

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  group?: string;
}

const navItems: NavItem[] = [
  { label: "Home", path: "/", icon: <Home className="w-4 h-4" /> },
  { label: "Recover", path: "/recover", icon: <Zap className="w-4 h-4" />, group: "Recover" },
  { label: "Discover", path: "/discover", icon: <Compass className="w-4 h-4" />, group: "Recover" },
  { label: "Understand", path: "/understand", icon: <BarChart2 className="w-4 h-4" />, group: "Intelligence" },
  { label: "Manage", path: "/manage", icon: <ListChecks className="w-4 h-4" />, group: "Operations" },
  { label: "Transactions", path: "/transactions", icon: <Database className="w-4 h-4" />, group: "Operations" },
  { label: "Protect", path: "/protect", icon: <ShieldCheck className="w-4 h-4" />, group: "Operations" },
  { label: "Track", path: "/track", icon: <Clock className="w-4 h-4" />, group: "Operations" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  let lastGroup = "";

  return (
    <nav className="flex flex-col gap-0.5 px-3 py-3" role="navigation" aria-label="Main navigation">
      {navItems.map((item) => {
        const active = isActive(item.path);
        const showGroup = item.group && item.group !== lastGroup;
        if (item.group) lastGroup = item.group;

        return (
          <div key={item.path}>
            {showGroup && (
              <p className="text-[10px] font-semibold text-text-subtle uppercase tracking-widest mt-5 mb-1.5 px-3 select-none">
                {item.group}
              </p>
            )}
            {!item.group && <div className="mb-1" />}
            <Link
              to={item.path}
              onClick={onNavigate}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
                active
                  ? "bg-accent-light text-accent"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-overlay"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <span className={`flex-shrink-0 ${active ? "text-accent" : "text-text-subtle"}`}>
                {item.icon}
              </span>
              {item.label}
            </Link>
          </div>
        );
      })}
    </nav>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface-base flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col w-56 border-r border-surface-border bg-surface-raised fixed inset-y-0 left-0 z-30 shadow-sidebar">
        <div className="flex items-center h-14 px-5 border-b border-surface-border flex-shrink-0">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-[15px] font-bold text-text-primary tracking-tight">
              Recover<span className="text-accent">IQ</span>
            </span>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto">
          <NavLinks />
        </div>


      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-surface-raised border-r border-surface-border transform transition-transform duration-300 lg:hidden ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between h-14 px-5 border-b border-surface-border">
          <Link
            to="/"
            className="text-[15px] font-bold text-text-primary tracking-tight"
            onClick={() => setSidebarOpen(false)}
          >
            Recover<span className="text-accent">IQ</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 text-text-muted hover:text-text-primary transition-colors rounded"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="overflow-y-auto">
          <NavLinks onNavigate={() => setSidebarOpen(false)} />
        </div>

      </aside>

      {/* Main content */}
      <div className="flex-1 lg:ml-56 flex flex-col min-h-screen">
        {/* Mobile top bar */}
        <header className="lg:hidden sticky top-0 z-20 bg-surface-raised/95 backdrop-blur-sm border-b border-surface-border">
          <div className="flex items-center h-14 px-4">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 -ml-1.5 text-text-muted hover:text-text-primary transition-colors rounded"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
            <Link to="/" className="text-[15px] font-bold text-text-primary tracking-tight ml-3">
              Recover<span className="text-accent">IQ</span>
            </Link>
          </div>
        </header>

        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

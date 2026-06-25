"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BookOpen,
  MessageSquare,
  Smartphone,
  Play,
  Settings,
  LogOut,
  Bot,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/auth-store";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { href: "/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/evaluation", label: "Evaluasi", icon: BarChart3 },
  { href: "/sessions", label: "WhatsApp Session", icon: Smartphone },
  { href: "/playground", label: "Playground", icon: Play },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);

  return (
    <aside className="flex h-full w-64 flex-col border-r border-border bg-card">
      <div className="flex items-center gap-3 border-b border-border px-6 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary">
          <Bot className="h-5 w-5 text-primary-foreground" />
        </div>
        <span className="font-heading text-[20px] font-[900] tracking-tight text-ink">
          MindSync
        </span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-4 py-2.5 text-[14px] font-semibold transition-all duration-150",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-canvas-soft hover:text-ink"
              )}
            >
              <Icon className="h-[18px] w-[18px]" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <button
          onClick={() => {
            logout();
            window.location.href = "/login";
          }}
          className="flex w-full items-center gap-3 rounded-xl px-4 py-2.5 text-[14px] font-semibold text-muted-foreground transition-all duration-150 hover:bg-canvas-soft hover:text-ink"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Logout
        </button>
      </div>
    </aside>
  );
}

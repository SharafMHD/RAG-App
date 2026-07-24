"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, MessageSquare, Settings } from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin/knowledge-bases", label: "Knowledge Bases", description: "Create, upload, process", icon: Database },
  { href: "/admin/settings", label: "Settings", description: "Health and defaults", icon: Settings },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="admin-sidebar">
      <div className="brand-row">
        <div className="brand-mark">A</div>
        <div>
          <strong>Admin</strong>
          <span>RAG operations</span>
        </div>
      </div>

      <nav className="admin-nav" aria-label="Admin navigation">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link className={active ? "active" : ""} href={item.href} key={item.href}>
              <Icon size={17} />
              <span className="nav-copy"><strong>{item.label}</strong><small>{item.description}</small></span>
            </Link>
          );
        })}
      </nav>

      <Link className="back-to-chat" href="/">
        <MessageSquare size={17} /> Back to Chat
      </Link>
    </aside>
  );
}

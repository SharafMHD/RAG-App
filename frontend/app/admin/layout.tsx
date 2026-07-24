import type { ReactNode } from "react";
import { AdminSidebar } from "@/components/admin/admin-sidebar";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <main className="admin-shell">
      <AdminSidebar />
      <section className="admin-content">{children}</section>
    </main>
  );
}

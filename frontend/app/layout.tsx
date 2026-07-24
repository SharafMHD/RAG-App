import type { Metadata } from "next";
import "sweetalert2/dist/sweetalert2.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Chat",
  description: "Cited chat UI for the FastAPI RAG backend",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

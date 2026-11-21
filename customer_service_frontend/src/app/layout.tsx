import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "电商智能客服",
  description: "基于 LangGraph 的智能客服系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      {/* 确保 body 没有任何多余的 margin 和 padding */}
      <body className="m-0 p-0">{children}</body>
    </html>
  );
}
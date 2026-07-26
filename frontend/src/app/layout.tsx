import { Providers } from "../components/Providers";
import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // 加上 suppressHydrationWarning，讓 React 忽略瀏覽器套件注入屬性產生的警告
    <html lang="zh-TW" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
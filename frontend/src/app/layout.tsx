import "./globals.css";
import { Providers } from "@/components/Providers";
import OrgProvider from "@/components/OrgProvider";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // 加上 suppressHydrationWarning 屬性
    <html lang="zh-TW" suppressHydrationWarning>
      <body>
        <Providers>
          <OrgProvider>
            {children}
          </OrgProvider>
        </Providers>
      </body>
    </html>
  );
}
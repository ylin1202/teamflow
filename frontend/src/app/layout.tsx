import "./globals.css";
import { Providers } from "@/components/Providers";
import OrgProvider from "@/components/OrgProvider";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
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
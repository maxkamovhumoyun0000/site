import type { Metadata, Viewport } from "next";
import Script from "next/script";
import PwaRegister from "./pwa-register";
import { ThemeProvider } from "./ui/theme-provider";
import { RootWebLocaleProvider } from "./ui/web-i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Diamond Education",
  description: "Diamond Education - Ingliz va Rus tillari hamda turli fanlar bo'yicha zamonaviy o'quv markazi. Sifatli ta'lim, interaktiv onlayn platforma va professional ustozlar.",
  applicationName: "Diamond Education",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Diamond Education",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: "/logo.jpg",
    apple: "/logo.jpg",
  },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#1123D6",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
};

import { GlobalVoiceRoomProvider } from "./ui/voice-room/GlobalVoiceRoomContext";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    "name": "Diamond Education",
    "alternateName": "Diamond Education uz",
    "url": "https://diamond-education.uz",
    "logo": "https://diamond-education.uz/logo.jpg",
    "image": "https://diamond-education.uz/logo.jpg",
    "description": "Diamond Education - Ingliz va Rus tillari hamda turli fanlar bo'yicha zamonaviy o'quv markazi. Sifatli ta'lim, interaktiv onlayn platforma va professional ustozlar.",
    "telephone": "+998-97-748-36-34",
    "sameAs": [
      "https://www.instagram.com/diamond_education_",
      "https://t.me/diamond_education1"
    ],
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Yangiyul",
      "addressRegion": "Tashkent Region",
      "addressCountry": "UZ"
    }
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/logo.jpg" type="image/jpeg" />
        <link rel="shortcut icon" href="/logo.jpg" type="image/jpeg" />
        <link rel="apple-touch-icon" href="/logo.jpg" />
        <link rel="preconnect" href="https://telegram.org" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://telegram.org" />
        <meta name="keywords" content="Diamond Education, Diamond Education uz, O'quv markazi, Yangiyo'l o'quv markazi, Ingliz tili kurslari, Rus tili kurslari" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <PwaRegister />
        <RootWebLocaleProvider>
          <ThemeProvider>
            <GlobalVoiceRoomProvider>
              {children}
            </GlobalVoiceRoomProvider>
          </ThemeProvider>
        </RootWebLocaleProvider>
      </body>
    </html>
  );
}

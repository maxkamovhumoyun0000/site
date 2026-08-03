import type { Metadata, Viewport } from "next";
import Script from "next/script";
import PwaRegister from "./pwa-register";
import { ThemeProvider } from "./ui/theme-provider";
import { RootWebLocaleProvider } from "./ui/web-i18n";
import { Inter_Tight, Manrope, Sora, Outfit, Plus_Jakarta_Sans, Inter } from "next/font/google";
import "./globals.css";

const interTight = Inter_Tight({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-inter-tight", display: "swap" });
const manrope = Manrope({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"], variable: "--font-manrope", display: "swap" });
const sora = Sora({ subsets: ["latin"], weight: ["500", "600", "700", "800"], variable: "--font-sora", display: "swap" });
const outfit = Outfit({ subsets: ["latin"], weight: ["400", "600", "800", "900"], variable: "--font-outfit", display: "swap" });
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "500", "700", "800"], variable: "--font-jakarta", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

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
    <html lang="en" suppressHydrationWarning className={`${interTight.variable} ${manrope.variable} ${sora.variable} ${outfit.variable} ${jakarta.variable} ${inter.variable}`}>
      <head>
        <link rel="icon" href="/logo.jpg" type="image/jpeg" />
        <link rel="shortcut icon" href="/logo.jpg" type="image/jpeg" />
        <link rel="apple-touch-icon" href="/logo.jpg" />
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

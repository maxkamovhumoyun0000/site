import { Manrope, Sora } from 'next/font/google'
import { AuthProvider } from '@/lib/auth-context'
import './globals.css'

const manrope = Manrope({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-sans'
})

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-serif'
})

export const metadata = {
  title: 'Diamond Education',
  description: 'Diamond Education platformasi',
  icons: {
    icon: '/favicon.ico',
  },
}

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#1123D6',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${manrope.variable} ${sora.variable}`}>
      <head>
        {/* Telegram WebApp Script - Required for Mini App functionality */}
        <script src="https://telegram.org/js/telegram-web-app.js" async />
      </head>
      <body className="font-sans antialiased">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}

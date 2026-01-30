import type { Metadata, Viewport } from 'next'
import './globals.css'
import Providers from './providers'

export const viewport: Viewport = {
  themeColor: '#4ecdc4',
}

export const metadata: Metadata = {
  title: 'OpenFDA Explorer - Medical Device Intelligence',
  description: 'Explore FDA medical device data with AI-powered insights',
  metadataBase: new URL('https://openfda-agent.snambiar.com'),
  icons: {
    icon: [{ url: '/favicon.ico' }],
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    title: 'OpenFDA Explorer',
    description: 'Explore FDA medical device data with AI-powered insights',
    type: 'website',
    url: 'https://openfda-agent.snambiar.com',
    siteName: 'OpenFDA Explorer',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

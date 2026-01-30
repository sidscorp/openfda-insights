import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'FDA Lookup - Medical Device & Manufacturer Search',
  description: 'Search and explore FDA medical device data, manufacturer reports, and safety information',
}

export default function LookupLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

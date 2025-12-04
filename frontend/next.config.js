/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === 'production'
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || (isProd ? '/fda' : '')

const nextConfig = {
  output: 'export',
  basePath,
  assetPrefix: basePath || undefined,
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  // Environment variables for API endpoint
  env: {
    NEXT_PUBLIC_API_URL: isProd
      ? 'https://portfolio.snambiar.com/fda/api'
      : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api',
  },
}

module.exports = nextConfig

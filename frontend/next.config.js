/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath: '/fda',
  assetPrefix: '/fda',
  images: {
    unoptimized: true
  },
  trailingSlash: true,
  // Environment variables for API endpoint
  env: {
    NEXT_PUBLIC_API_URL: process.env.NODE_ENV === 'production' 
      ? 'https://portfolio.snambiar.com/fda/api'
      : 'http://localhost:8001/api'
  }
}

module.exports = nextConfig
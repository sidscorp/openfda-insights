/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === 'production'

const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_API_URL: isProd
      ? '/api'
      : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api',
  },
}

module.exports = nextConfig

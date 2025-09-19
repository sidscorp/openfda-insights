/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath: '/fda-explorer-app',
  images: {
    unoptimized: true
  },
  trailingSlash: true
}

module.exports = nextConfig
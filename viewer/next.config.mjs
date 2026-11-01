const nextConfig = {
  output: 'export',
  trailingSlash: true,
  poweredByHeader: false,
  experimental: { cpus: 2 },
  turbopack: { root: process.cwd() },
};
export default nextConfig;

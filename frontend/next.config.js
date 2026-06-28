/** @type {import('next').NextConfig} */
const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:4210";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

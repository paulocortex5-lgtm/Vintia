import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000";

const siteDescription =
  "Vantia finds visa-sponsored jobs and funded scholarships, scores your CV " +
  "against real ATS rules, and drafts targeted cover letters — targeted, " +
  "verified, and free of third-party intermediaries.";

// Task 5.4: schema.org WebSite + Organization JSON-LD, rendered on every page.
const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Vantia",
  url: baseUrl,
  description: siteDescription,
  inLanguage: "en",
  publisher: {
    "@type": "Organization",
    name: "Vantia",
    url: baseUrl,
  },
};

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "Vantia — verified jobs, scholarships & application tools",
    template: "%s | Vantia",
  },
  description: siteDescription,
  keywords: [
    "visa sponsorship jobs",
    "funded scholarships",
    "ATS resume score",
    "cover letter generator",
    "CV improvement",
  ],
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: baseUrl,
    siteName: "Vantia",
    title: "Vantia — verified jobs, scholarships & application tools",
    description: siteDescription,
  },
  twitter: {
    card: "summary",
    title: "Vantia — verified jobs, scholarships & application tools",
    description: siteDescription,
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        {children}
      </body>
    </html>
  );
}
